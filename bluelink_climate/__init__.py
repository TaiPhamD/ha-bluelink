from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN  # Make sure DOMAIN matches your integration's domain
from .climate import BluelinkClimateControl

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up bluelink_climate from a config entry."""
    # Initialize your BluelinkClimateControl with the configuration data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = BluelinkClimateControl(
        host=entry.data["host"],
        port=entry.data["port"],
        api_key=entry.data["api_key"],
        air_temperature=entry.data["air_temperature"]
    )

    # Forward the setup to the climate platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )

    return True
