import logging
import time
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, BLUELINK_CLIMATE_MAX_TIMER, BLUELINK_SWITCH_TOGGLE_TIMEOUT
from .bluelink_api import Bluelink
from .utils import get_base_host

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up BluelinkClimateSwitch from a config entry."""

    # Retrieve the existing instance of BluelinkClimateSwitch from hass.data
    switch_entity = hass.data[DOMAIN][entry.entry_id]["switch"]

    async_add_entities([switch_entity], True)


class BluelinkClimateSwitch(SwitchEntity):
    def __init__(self, host, port, api_key, shared_data):
        self._is_on = False
        # create unique identifier
        base_url = get_base_host(host)
        self._unique_identifier = f"{base_url}_bluelink_switch"
        self._shared_data = shared_data
        self._bluelink_api = Bluelink(host=host, port=port, api_key=api_key)
        self._auto_off_timer = None
        self._cooldown_period = BLUELINK_SWITCH_TOGGLE_TIMEOUT
        self._last_toggle_time = 0

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_identifier

    @property
    def name(self):
        return "Bluelink Climate Switch"

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        if time.time() - self._last_toggle_time < self._cooldown_period:
            _LOGGER.warning("Switch recently toggled, please wait before toggling again.")
            return  # Exit the method to prevent toggling
        self._bluelink_api.set_climate("on", self._shared_data.get_data())
        self._is_on = True
        # Schedule the switch to turn off after 10 minutes
        self._auto_off_timer = async_call_later(self.hass, BLUELINK_CLIMATE_MAX_TIMER, self._auto_turn_off)
        self.schedule_update_ha_state()
        self._last_toggle_time = time.time()


    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if time.time() - self._last_toggle_time < self._cooldown_period:
            _LOGGER.warning("Switch recently toggled, please wait before toggling again.")
            return  # Exit the method to prevent toggling          
        self._bluelink_api.set_climate("off")
        self._cancel_auto_off_timer()
        self._is_on = False
        self.schedule_update_ha_state()
        self._last_toggle_time = time.time()

    def _auto_turn_off(self, _):
        """Turn the switch off automatically."""
        self._cancel_auto_off_timer()
        self._is_on = False
        self.schedule_update_ha_state()

    def _cancel_auto_off_timer(self):
        """Cancel the auto-off timer."""
        if self._auto_off_timer:
            self._auto_off_timer()
            self._auto_off_timer = None