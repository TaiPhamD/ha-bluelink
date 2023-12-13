from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN  # Make sure DOMAIN matches your integration's domain
from .climate import BluelinkClimateControl
from .switch import BluelinkClimateSwitch
from .shared_data import SharedData
from .bluelink_api import BluelinkAPI


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up bluelink_climate from a config entry."""

    # Share temp data between climate_control and climate_switch
    shared_data = SharedData(hass)
    await shared_data.load_data()
    # Store both the climate control instance and shared data in a dictionary
    bluelink_api = BluelinkAPI(
        username=entry.data["username"],
        password=entry.data["password"],
        pin=entry.data["pin"],
        vin=entry.data["vin"],
    )

    await hass.async_add_executor_job(bluelink_api.login)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        # Initialize and store the switch instance
        "switch": BluelinkClimateSwitch(
            shared_data=shared_data,
            vin=entry.data["vin"],
            bluelink_api=bluelink_api,
        ),
        "climate": BluelinkClimateControl(
            shared_data=shared_data,
            vin=entry.data["vin"],
        ),
    }

    # Forward the setup to the switch entity
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "switch"),
    )
    # Forward the setup to the climate entity
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )
    return True
