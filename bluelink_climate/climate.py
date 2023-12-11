import requests
import logging
import json
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE, 
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF
)
from homeassistant.const import (
    TEMP_FAHRENHEIT,
    ATTR_TEMPERATURE
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up BluelinkClimateControl from a config entry."""
    config = entry.data
    climate_entity = BluelinkClimateControl(
        host=config["host"],
        port=config["port"],
        api_key=config["api_key"],
        air_temperature=config["air_temperature"]
    )

    async_add_entities([climate_entity], True)
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up BluelinkClimateControl from a config entry."""
    config = entry.data
    climate_entity = BluelinkClimateControl(
        host=config["host"],
        port=config["port"],
        api_key=config["api_key"],
        air_temperature=config["air_temperature"]
    )

    async_add_entities([climate_entity], True)

# def setup_platform(hass, config, add_entities, discovery_info=None):
#     host = config[CONF_HOST]
#     port = config[CONF_PORT]
#     api_key = config["api_key"]
#     air_temperature = config["air_temperature"]
    
#     add_entities([BluelinkClimateControl(host, port, api_key, air_temperature)])

class BluelinkClimateControl(ClimateEntity):
    def __init__(self, host, port, api_key, air_temperature):
        self._host = host
        self._port = port
        self._api_key = api_key
        self._temperature = air_temperature
        self._attr_hvac_mode = HVAC_MODE_OFF  # Default to off
        self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE
        self._unique_identifier = "bluelink_climate_control"
        self._auto_off_timer = None

    @property
    def supported_features(self):
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def hvac_modes(self):
        return [HVAC_MODE_HEAT_COOL, HVAC_MODE_OFF]

    @property
    def temperature_unit(self):
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        return self._temperature

    @property
    def target_temperature(self):
        return self._temperature

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_identifier

    @property
    def name(self):
        return "Bluelink Climate Control"

    def set_temperature(self, **kwargs):
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            self._temperature = temperature
            self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode):
        """Set new target HVAC mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self._turn_off_climate_control()
        elif hvac_mode == HVAC_MODE_HEAT_COOL:
            self._turn_on_climate_control()
        self._attr_hvac_mode = hvac_mode
        self.schedule_update_ha_state()

    def _turn_off_climate_control(self):
        # Implement the logic to turn off the climate control
        if self._auto_off_timer:
            self._auto_off_timer.cancel()
            self._auto_off_timer = None
        self._call_api("off")  # Example API call
    def _turn_on_climate_control(self):
        # Implement the logic to turn on the climate control
        self._call_api("on")  # Example API call
        self._start_auto_off_timer()

    def _start_auto_off_timer(self):
        if self._auto_off_timer:
            self._auto_off_timer.cancel()

        def auto_off():
            self._attr_hvac_mode = HVAC_MODE_OFF
            self.schedule_update_ha_state()
            self._auto_off_timer = None

        self._auto_off_timer = self.hass.loop.call_later(600, auto_off)  # 600 seconds = 10 minutes

    def _call_api(self, command):
        """Call the Blue Link API with the appropriate command."""
        url = f"{self._host}:{self._port}/api/"
        payload = {"api_key": self._api_key}

        if command == "on":
            url += "start_climate"
            payload["air_temperature"] = self._temperature
            # convert air_temperature from int to string
            payload["air_temperature"] = str(payload["air_temperature"])
        elif command == "off":
            url += "stop_climate"
        # set request as post and data payload as json
        payload = json.dumps(payload)

        response = requests.post(url, data=payload)
        if response.status_code == 200:
            _LOGGER.info(f"API call successful: {response.text}")
        else:
            _LOGGER.error(f"API call failed: {response.text}")
    # Add methods for HVAC mode if needed
