import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN  # Make sure DOMAIN matches your integration's domain
from .climate import BluelinkClimateControl
from .switch import BluelinkClimateSwitch
from .shared_data import SharedData
from .bluelink_api import BluelinkAPI
from .config_flow import BluelinkConfigFlow  # Import your config flow

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up bluelink_climate from a config entry."""

    # Share temp data between climate_control and climate_switch
    shared_data = SharedData(hass)
    await shared_data.load_data()

    bluelink_api = BluelinkAPI(
        username=entry.data["username"],
        password=entry.data["password"],
        pin=entry.data["pin"],
        auth=entry.data["auth"]
    )
    bluelink_api.store_vehicle_info(entry.data["selected_vehicle_vin"], entry.data["selected_vehicle_reg_id"])

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "switch": BluelinkClimateSwitch(
            shared_data=shared_data,
            vin=entry.data["selected_vehicle_vin"],
            bluelink_api=bluelink_api,
        ),
        "climate": BluelinkClimateControl(
            shared_data=shared_data,
            vin=entry.data["selected_vehicle_vin"],
        ),
    }

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "switch"),
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = all(
        await asyncio.gather(
            hass.config_entries.async_forward_entry_unload(entry, Platform.SWITCH),
            hass.config_entries.async_forward_entry_unload(entry, Platform.CLIMATE)
        )
    )

    # Remove the config entry from hass.data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
