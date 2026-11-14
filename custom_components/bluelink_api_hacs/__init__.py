"""Hyundai USA Bluelink climate control."""

import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .bluelink_api import BluelinkAPI, BluelinkAuthError, BluelinkError
from .shared_data import SharedData

PLATFORMS = [
    Platform.CLIMATE,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]
type BluelinkConfigEntry = ConfigEntry[SharedData]


def _create_client(data):
    api = BluelinkAPI(data["username"], data["password"], data["pin"], data.get("auth"))
    try:
        api.store_vehicle_info(
            data["selected_vehicle_vin"],
            data["selected_vehicle_reg_id"],
            data.get("vehicle_generation", "2"),
        )
        api.ensure_authenticated()
    except Exception:
        api.close()
        raise
    return api


async def async_setup_entry(hass: HomeAssistant, entry: BluelinkConfigEntry) -> bool:
    """Validate authentication and await platform setup."""
    try:
        api = await hass.async_add_executor_job(_create_client, entry.data)
    except BluelinkAuthError as err:
        raise ConfigEntryAuthFailed("Sign in to Bluelink again") from err
    except (requests.RequestException, BluelinkError) as err:
        raise ConfigEntryNotReady("Unable to connect to Bluelink") from err
    runtime = entry.runtime_data = SharedData(hass, entry, api)
    try:
        await runtime.load_data()
        await runtime.async_initialize()
        runtime.save_auth()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await runtime.async_close()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BluelinkConfigEntry) -> bool:
    """Unload platforms and cancel pending callbacks."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_close()
    return unload_ok
