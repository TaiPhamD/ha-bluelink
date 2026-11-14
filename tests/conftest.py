"""Fixtures for the custom Bluelink integration."""

from unittest.mock import Mock

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow the test HA instance to load this integration."""


@pytest.fixture
def credentials():
    return {"username": "test@example.com", "password": "secret", "pin": "0123"}


@pytest.fixture
def auth():
    return {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": 4102444800,
    }


@pytest.fixture
def vehicle():
    return {
        "vin": "TESTVIN",
        "reg_id": "registration",
        "nickname": "IONIQ 5",
        "gen": "2",
    }


@pytest.fixture
def api(auth):
    client = Mock()
    client.auth = auth
    return client
