from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN  # Make sure DOMAIN matches your integration's domain
from .climate import BluelinkClimateControl
from .shared_data import SharedData

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up bluelink_climate from a config entry."""

    # Initialize SharedData class to share temperature data between switch and climate
    shared_data = SharedData(hass)
    await shared_data.load_data()
    # Store both the climate control instance and shared data in a dictionary
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        'climate_control': BluelinkClimateControl(
            host=entry.data["host"],
            port=entry.data["port"],
            api_key=entry.data["api_key"],
            shared_data=shared_data
        )
    }

    # Forward the setup to the climate platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )

    return True
