"""Synchronous client for Hyundai's USA telematics API.

Construct and call this client in Home Assistant's executor, including SSL setup.
"""

import ssl
import time
from copy import deepcopy

import requests
from requests.adapters import HTTPAdapter
from urllib3 import PoolManager

from .const import BASE_URL
from .vehicle_status import VehicleStatus

REQUEST_TIMEOUT = 30


class BluelinkError(Exception):
    """The server rejected a request or returned an invalid response."""


class BluelinkAuthError(BluelinkError):
    """The account needs to authenticate again."""


class BluelinkMFARequired(BluelinkAuthError):
    """Hyundai requested an interactive challenge instead of an API token."""


class CustomHttpAdapter(HTTPAdapter):
    """Keep certificate verification while supporting Hyundai's legacy TLS."""

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        context = ssl.create_default_context()
        context.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=context,
            **kwargs,
        )


class BluelinkAPI:
    """Manage credentials, token renewal, and remote climate commands."""

    def __init__(self, username, password, pin, auth=None):
        self._client_id = "m66129Bb-em93-SPAHYN-bZ91-am4540zp19920"
        self._client_secret = "v558o935-6nne-423i-baa8"
        self._session = requests.Session()
        self._session.mount(BASE_URL, CustomHttpAdapter())
        self._username = username
        self._password = password
        self._pin = pin
        # Config entry data must never be mutated by the executor thread.
        self._auth = deepcopy(auth or {})

    @property
    def auth(self):
        """Return a snapshot suitable for saving in a config entry."""
        return deepcopy(self._auth)

    def close(self):
        """Release connections."""
        self._session.close()

    def _headers(self):
        return {
            "client_id": self._client_id,
            "clientId": self._client_id,
            "clientSecret": self._client_secret,
            "User-Agent": "okhttp/3.12.0",
            "Content-Type": "application/json",
            "from": "SPA",
            "to": "ISS",
            "brandIndicator": "H",
        }

    def _request(self, method, path, **kwargs):
        response = self._session.request(
            method, f"{BASE_URL}{path}", timeout=REQUEST_TIMEOUT, **kwargs
        )
        if response.status_code in (401, 403):
            raise BluelinkAuthError("Hyundai rejected the credentials or token")
        response.raise_for_status()
        return response

    @staticmethod
    def _json(response):
        try:
            data = response.json()
        except ValueError as err:
            raise BluelinkError("Hyundai returned an invalid response") from err
        if not isinstance(data, dict):
            raise BluelinkError("Hyundai returned an invalid response")
        if data.get("errorCode"):
            if str(data["errorCode"]) in {"401", "403"}:
                raise BluelinkAuthError("Hyundai rejected the credentials or token")
            raise BluelinkError("Hyundai reported an API error")
        return data

    def _store_auth(self, data):
        if not data.get("access_token") and (
            data.get("password_token") or data.get("mfa_token")
        ):
            raise BluelinkMFARequired("Hyundai requires interactive verification")
        if not data.get("access_token"):
            raise BluelinkAuthError("Login did not return an access token")
        try:
            duration = float(data["expires_in"])
            if duration <= 0:
                raise ValueError
        except (KeyError, TypeError, ValueError) as err:
            raise BluelinkError("Invalid token expiration returned by Hyundai") from err
        self._auth.update(
            {
                "access_token": data["access_token"],
                "refresh_token": data.get(
                    "refresh_token", self._auth.get("refresh_token")
                ),
                "expires_in": duration,
                "expires_at": time.time() + duration,
                "username": data.get("username", self._username),
                "pin": self._pin,
            }
        )
        return self.auth

    def login(self):
        """Authenticate using the USA telematics endpoint."""
        response = self._request(
            "POST",
            "/v2/ac/oauth/token",
            headers=self._headers(),
            json={"username": self._username, "password": self._password},
        )
        return self._store_auth(self._json(response))

    def ensure_authenticated(self):
        """Refresh expired tokens, falling back to password authentication."""
        if (
            self._auth.get("access_token")
            and time.time() < self._auth.get("expires_at", 0) - 60
        ):
            return self.auth
        if self._auth.get("refresh_token"):
            try:
                response = self._request(
                    "POST",
                    "/v2/ac/oauth/token",
                    headers=self._headers(),
                    json={
                        "username": self._username,
                        "password": self._password,
                        "grant_type": "refresh_token",
                        "refresh_token": self._auth["refresh_token"],
                    },
                )
                return self._store_auth(self._json(response))
            except (BluelinkAuthError, BluelinkError):
                pass
            except requests.HTTPError as err:
                if err.response is None or err.response.status_code != 400:
                    raise
        return self.login()

    def get_enrollment_details(self):
        self.ensure_authenticated()
        headers = self._headers() | {"access_token": self._auth["access_token"]}
        return self._json(
            self._request(
                "GET", f"/ac/v2/enrollment/details/{self._username}", headers=headers
            )
        )

    @staticmethod
    def get_vehicles(enrollment_details):
        return [
            {
                "vin": details["vin"],
                "reg_id": details["regid"],
                "nickname": details.get("nickName") or details["vin"],
                "gen": details.get("vehicleGeneration"),
            }
            for item in enrollment_details.get("enrolledVehicleDetails", [])
            if (details := item.get("vehicleDetails"))
        ]

    def store_vehicle_info(self, vin, reg_id, generation="2"):
        self._auth.update(vin=vin, reg_id=reg_id, generation=str(generation))

    def _set_request_headers(self):
        return self._headers() | {
            "access_token": self._auth["access_token"],
            "accessToken": self._auth["access_token"],
            "username": self._username,
            "gen": self._auth.get("generation", "2"),
            "registrationId": self._auth["reg_id"],
            "VIN": self._auth["vin"],
            "APPCLOUD-VIN": self._auth["vin"],
            "Language": "0",
            "encryptFlag": "false",
            "bluelinkservicepin": self._pin,
            "offset": "-4",
        }

    def _command(self, path, **kwargs):
        self.ensure_authenticated()
        response = self._request(
            "POST", path, headers=self._set_request_headers(), **kwargs
        )
        # Commands may return HTTP 200 with an empty body.
        if response.content:
            self._json(response)
        return next(
            (
                response.headers[key]
                for key in ("tmsTid", "transactionId", "Xid")
                if isinstance(response.headers.get(key), str)
                and response.headers[key].strip()
            ),
            None,
        )

    def start_climate(self, temp=72):
        return self._command(
            "/ac/v2/evc/fatc/start",
            json={
                "airCtrl": 1,
                "airTemp": {"value": str(temp), "unit": 1},
                "heating1": 0,
                "defrost": False,
            },
        )

    def stop_climate(self):
        return self._command("/ac/v2/evc/fatc/stop")

    def get_vehicle_status(self, refresh=False):
        """Read Hyundai's cache; only explicitly requested refreshes wake the car."""
        self.ensure_authenticated()
        headers = self._set_request_headers()
        if refresh:
            headers["REFRESH"] = "true"
        data = self._json(
            self._request("GET", "/ac/v2/rcs/rvs/vehicleStatus", headers=headers)
        )
        status = data.get("vehicleStatus")
        if not isinstance(status, dict):
            raise BluelinkError("Hyundai returned no vehicle status")
        return VehicleStatus.from_response(status)

    def check_action_status(self, transaction_id):
        """Read command completion independently of cached vehicle telemetry."""
        self.ensure_authenticated()
        headers = self._set_request_headers() | {
            "tid": transaction_id,
            "login_id": self._username,
            "service_type": "REMOTE_POLL",
        }
        response = self._request("GET", "/ac/v2/rmt/getRunningStatus", headers=headers)
        if not response.content:
            return "pending"
        status = self._json(response).get("status")
        if not isinstance(status, str):
            return "pending"
        return {"SUCCESS": "succeeded", "ERROR": "failed"}.get(status, "pending")
