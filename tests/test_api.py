"""Exercise token renewal against HTTP responses without making network calls."""

import time
from unittest.mock import Mock, patch

import pytest
import requests

from custom_components.bluelink_api_hacs.bluelink_api import (
    BluelinkAPI,
    BluelinkAuthError,
    BluelinkError,
)


def response(data=None, status=200):
    result = Mock(
        status_code=status, content=b"json" if data is not None else b"", headers={}
    )
    result.json.return_value = data
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(response=result)
    return result


@pytest.fixture
def client(credentials):
    with patch("custom_components.bluelink_api_hacs.bluelink_api.requests.Session"):
        return BluelinkAPI(**credentials)


@pytest.mark.parametrize("expires_in", [1800, "1800", 1800.0])
def test_login_expiration_and_timeout(client, expires_in):
    client._session.request.return_value = response(
        {"access_token": "new", "refresh_token": "r", "expires_in": expires_in}
    )
    auth = client.login()
    assert time.time() + 1790 < auth["expires_at"] < time.time() + 1810
    assert client._session.request.call_args.kwargs["timeout"] == 30


def test_refresh_rotates_token_and_preserves_vehicle(client):
    original = {
        "access_token": "old",
        "refresh_token": "r",
        "expires_at": 0,
        "vin": "TESTVIN",
        "reg_id": "reg",
    }
    client._auth = original.copy()
    client._session.request.return_value = response(
        {"access_token": "new", "refresh_token": "rotated", "expires_in": 1800}
    )
    auth = client.ensure_authenticated()
    assert auth["refresh_token"] == "rotated"
    assert auth["vin"] == "TESTVIN"
    assert original["access_token"] == "old"
    args, kwargs = client._session.request.call_args
    assert args[1].endswith("/v2/ac/oauth/token")
    assert kwargs["json"]["grant_type"] == "refresh_token"
    assert kwargs["json"]["password"] == "secret"


def test_rejected_refresh_falls_back_to_login(client):
    client._auth = {"refresh_token": "expired"}
    client._session.request.side_effect = [
        response(status=401),
        response({"access_token": "new", "expires_in": "1800"}),
    ]
    assert client.ensure_authenticated()["access_token"] == "new"
    assert client._session.request.call_count == 2


def test_network_error_does_not_trigger_login_storm(client):
    client._auth = {"refresh_token": "r"}
    client._session.request.side_effect = requests.Timeout()
    with pytest.raises(requests.Timeout):
        client.ensure_authenticated()
    assert client._session.request.call_count == 1


def test_command_auth_failure_is_not_success(client, auth):
    client._auth = auth
    client.store_vehicle_info("vin", "reg")
    client._session.request.return_value = response(status=401)
    with pytest.raises(BluelinkAuthError):
        client.start_climate()


def test_empty_command_response_is_success(client, auth):
    client._auth = auth
    client.store_vehicle_info("vin", "reg")
    client._session.request.return_value = response()
    client.stop_climate()


def test_no_vehicles(client):
    assert client.get_vehicles({"enrolledVehicleDetails": []}) == []


@pytest.mark.parametrize("duration", [None, "invalid", -1, 0])
def test_invalid_expiry(client, duration):
    client._session.request.return_value = response(
        {"access_token": "a", "expires_in": duration}
    )
    with pytest.raises(BluelinkError):
        client.login()


@pytest.mark.parametrize("field", ["password_token", "mfa_token"])
def test_mfa_challenge_is_not_treated_as_token(client, field):
    from custom_components.bluelink_api_hacs.bluelink_api import BluelinkMFARequired

    client._session.request.return_value = response({field: "challenge"})
    with pytest.raises(BluelinkMFARequired):
        client.login()
    assert "access_token" not in client.auth


def test_auth_probe_redacts_all_values():
    import json

    from scripts.check_auth import response_structure

    report = json.dumps(
        response_structure(
            {
                "access_token": "secret-token",
                "username": "private@example.com",
                "nested": {"password": "hidden"},
            }
        )
    )
    assert "secret-token" not in report
    assert "private@example.com" not in report
    assert "hidden" not in report
    assert "access_token" in report


@pytest.mark.parametrize("header", ["tmsTid", "transactionId", "Xid"])
def test_command_returns_tracking_id(client, auth, header):
    client._auth = auth
    client.store_vehicle_info("vin", "reg")
    result = response()
    result.headers = {header: "transaction"}
    client._session.request.return_value = result
    assert client.start_climate() == "transaction"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("SUCCESS", "succeeded"),
        ("ERROR", "failed"),
        ("PENDING", "pending"),
        (None, "pending"),
    ],
)
def test_command_status_protocol(client, auth, raw, expected):
    client._auth = auth
    client.store_vehicle_info("vin", "reg")
    client._session.request.return_value = response({"status": raw})
    assert client.check_action_status("transaction") == expected
    headers = client._session.request.call_args.kwargs["headers"]
    assert headers["tid"] == "transaction"
    assert headers["service_type"] == "REMOTE_POLL"


@pytest.mark.parametrize("refresh", [False, True])
def test_vehicle_status_protocol(client, auth, refresh):
    client._auth = auth
    client.store_vehicle_info("vin", "reg", "3")
    client._session.request.return_value = response(
        {"vehicleStatus": {"airCtrlOn": False}}
    )
    assert client.get_vehicle_status(refresh).climate_on is False
    args, kwargs = client._session.request.call_args
    assert args[1].endswith("/rcs/rvs/vehicleStatus")
    assert (kwargs["headers"].get("REFRESH") == "true") is refresh
    assert kwargs["headers"]["gen"] == "3"
    assert kwargs["headers"]["accessToken"] == auth["access_token"]
