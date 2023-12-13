import logging
from typing import Any
from .const import DOMAIN, BASE_URL

_LOGGER = logging.getLogger(__name__)

import requests
import urllib3
import ssl

import json
import time


class CustomHttpAdapter(requests.adapters.HTTPAdapter):
    # "Transport adapter" that allows us to use custom ssl_context.

    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = urllib3.poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=self.ssl_context,
        )


def get_legacy_session():
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    session = requests.session()
    session.mount("https://", CustomHttpAdapter(ctx))
    return session


class BluelinkAPI:
    def __init__(self, username, password, pin, vin):
        self._client_id = "m66129Bb-em93-SPAHYN-bZ91-am4540zp19920"
        self._client_secret = "v558o935-6nne-423i-baa8"
        self._session = get_legacy_session()
        self._username = username
        self._password = password
        self._pin = pin
        self._vin = vin
        self._auth = None

    def login(self):
        url = f"{BASE_URL}/v2/ac/oauth/token"
        headers = {
            "clientId": self._client_id,
            "clientSecret": self._client_secret,
            "Content-Type": "application/json",
        }
        payload = {"username": self._username, "password": self._password}
        response = self._session.post(url, headers=headers, json=payload)
        response.raise_for_status()

        data = response.json()
        expires_in = data.get("expires_in")
        # Convert expires_in from string to int and calculate the expiry time
        expires_in_duration = int(expires_in) if expires_in.isdigit() else 0
        expires_at = int(time.time() + expires_in_duration)

        auth = {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_in": data["expires_in"],
            "expires_at": expires_at,
            "username": data["username"],
            "pin": self._pin,
            "vin": self._vin,
        }

        enrollment_details = self._get_enrollment_details(auth)
        reg_id = None
        for vehicle in enrollment_details["enrolledVehicleDetails"]:
            if vehicle["vehicleDetails"]["vin"] == self._vin:
                reg_id = vehicle["vehicleDetails"]["regid"]

        auth["reg_id"] = reg_id
        self._auth = auth

        return auth

    def _get_enrollment_details(self, auth):
        url = f"{BASE_URL}/ac/v2/enrollment/details/{auth['username']}"
        headers = {
            "access_token": auth["access_token"],
            "User-Agent": "okhttp/3.12.0",
            "client_id": self._client_id,
            "includeNonConnectedVehicles": "Y",
            "Host": "api.telematics.hyundaiusa.com",
        }
        response = self._session.get(url, headers=headers)
        response.raise_for_status()

        return response.json()

    def _refresh_token(self):
        url = f"{BASE_URL}/v2/ac/oauth/token/refresh"
        headers = {
            "User-Agent": "okhttp/3.12.0",
            "client_secret": self._client_secret,
            "client_id": self._client_id,
            "Content-Type": "application/json",
        }
        payload = {"refresh_token": self._auth["refresh_token"]}
        response = self._session.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"Error refreshing token: {response.status_code}")
            return None

        data = response.json()
        expires_in = data.get("expires_in")
        # Convert expires_in from string to int and calculate the expiry time
        expires_in_duration = int(expires_in) if expires_in.isdigit() else 0
        expires_at = int(time.time() + expires_in_duration)
        self._auth["access_token"] = data["access_token"]
        self._auth["refresh_token"] = data["refresh_token"]
        self._auth["expires_in"] = data["expires_in"]
        self._auth["expires_at"] = expires_at

    def _token_expired(self):
        """Check if the access token has expired"""
        return time.time() >= self._auth.get("expires_at", 0) - 5

    def _refresh_token_if_needed(self):
        """Refresh the token if it is about to expire. If refresh fails, attempt a full login."""
        if self._token_expired():
            previous_expires_at = self._auth.get("expires_at", 0)
            self._refresh_token()
            if (
                self._auth.get("expires_at", 0) <= previous_expires_at
            ):  # Check if expires_at was not updated
                # Attempt a full re-login if the refresh token did not update 'expires_at'
                self._auth = self.login()
                if (
                    self._token_expired()
                ):  # Check again if the token is still expired after re-login
                    _LOGGER.warning("Error: Unable to refresh token or re-login.")
                    return False
        return True

    def _set_request_headers(self):
        return {
            "access_token": self._auth["access_token"],
            "client_id": self._client_id,
            "User-Agent": "okhttp/3.12.0",
            "Host": "api.telematics.hyundaiusa.com",
            "registrationId": self._auth["reg_id"],
            "VIN": self._auth["vin"],
            "APPCLOUD-VIN": self._auth["vin"],
            "Language": "0",
            "to": "ISS",
            "encryptFlag": "false",
            "from": "SPA",
            "brandIndicator": "H",
            "bluelinkservicepin": self._auth["pin"],
            "offset": "-4",
            "Content-Type": "application/json",
        }

    def start_climate(self, temp=72):
        if not self._refresh_token_if_needed():
            _LOGGER.warning( "Authentication failed. Unable to start climate control.")

        url = f"{BASE_URL}/ac/v2/evc/fatc/start"
        headers = self._set_request_headers()
        payload = {
            "airCtrl": 1,
            "airTemp": {"value": str(temp), "unit": 1},
            "heating1": 0,
            "defrost": False,
        }
        response = self._session.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            _LOGGER.warning(f"Error starting climate control: {response.status_code}")
            return None

        return response

    def stop_climate(self):
        if not self._refresh_token_if_needed():
            _LOGGER.warning("Authentication failed. Unable to stop climate control.")

        url = f"{BASE_URL}/ac/v2/evc/fatc/stop"
        headers = self._set_request_headers()
        response = self._session.post(url, headers=headers)
        if response.status_code != 200:
            _LOGGER.warning(f"Error stopping climate control: {response.status_code}")
            return None
        return response
