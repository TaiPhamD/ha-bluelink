from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN  # Make sure DOMAIN matches your integration's domain
from .climate import BluelinkClimateControl
from .switch import BluelinkClimateSwitch
from .shared_data import SharedData

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up bluelink_climate from a config entry."""

    # Share temp data between climate_control and climate_switch  
    shared_data = SharedData(hass)
    await shared_data.load_data()
    # Store both the climate control instance and shared data in a dictionary

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
         # Initialize and store the switch instance
        'switch': BluelinkClimateSwitch(
            host=entry.data["host"],
            port=entry.data["port"],
            api_key=entry.data["api_key"],
            shared_data=shared_data ),
        'climate': BluelinkClimateControl(
            host=entry.data["host"],
            port=entry.data["port"],    
            shared_data=shared_data,
        )
    }

    # Forward the setup to the switch platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "switch"),
    )   

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )
    return True
