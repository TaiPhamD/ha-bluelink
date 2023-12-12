import requests
import logging
import json
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode
)
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_ON,
    FAN_OFF    
)
from homeassistant.const import (
    TEMP_FAHRENHEIT,
    ATTR_TEMPERATURE
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_MAX_TEMP = 75
DEFAULT_MIN_TEMP = 55

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up BluelinkClimateControl from a config entry."""
    # Retrieve the existing instance of BluelinkClimateControl from hass.data
    climate_entity = hass.data[DOMAIN][entry.entry_id]['climate_control']
    async_add_entities([climate_entity], True)

class BluelinkClimateControl(ClimateEntity):
    def __init__(self, host, port, api_key, shared_data):
        self._host = host
        self._port = port
        self._api_key = api_key
        self._shared_data = shared_data
        self._temperature = self._shared_data.get_data()
        self._attr_hvac_mode = HVACMode.COOL # Set default to 'auto' mode
        self._attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.COOL, HVACMode.OFF]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._unique_identifier = "bluelink_climate_control"
        self._fan_mode = FAN_ON  # Default fan mode
        #self._fan_modes = ['on', 'off']  # Available fan modes
        self._fan_modes = [FAN_ON, FAN_OFF]
        #self._fan_modes = [FAN_ON, FAN_OFF]
        self._auto_off_timer = None

    @property
    def supported_features(self):
        return self._attr_supported_features
    
    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        #return 
        return self._fan_modes  
    
    @property
    def fan_mode(self):
        """Return the current fan mode."""
        return self._fan_mode

    
    @property
    def hvac_modes(self):
        return self._attr_hvac_modes 

    @property
    def temperature_unit(self):
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        return self._shared_data.get_data()

    @property
    def target_temperature(self):
        #return self._temperature
        return self._shared_data.get_data()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_identifier

    @property
    def name(self):
        return "Bluelink Climate Control"

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            self._temperature = temperature
            await self._shared_data.store_data(temperature)
            #asyncio.create_task(self._shared_data.store_data(temperature))
            #_LOGGER.warning(f"set_temperature temp: {self._temperature}")
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

    def set_hvac_mode(self, hvac_mode):
        """Set new target HVAC mode."""
        if hvac_mode == HVACMode.COOL or hvac_mode == HVACMode.OFF:
            self._turn_off_climate_control()
        elif hvac_mode == HVACMode.HEAT_COOL:
            self._turn_on_climate_control()
        self._attr_hvac_mode = hvac_mode
        self.schedule_update_ha_state()
        
    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode in self._fan_modes:
            self._fan_mode = fan_mode
            if fan_mode == 'on':
                self._turn_on_climate_control()
            elif fan_mode == 'off':
                self._turn_off_climate_control()
            self.schedule_update_ha_state()

    def _start_auto_off_timer(self):
        if self._auto_off_timer:
            self._auto_off_timer.cancel()

        def auto_off():
            self._attr_hvac_mode = HVACMode.COOL
            #self._fan_mode = FAN_OFF
            self.schedule_update_ha_state()
            self._auto_off_timer = None

        self._auto_off_timer = self.hass.loop.call_later(600, auto_off)  # 600 seconds = 10 minutes

    def _call_api(self, command):
        """Call the Blue Link API with the appropriate command."""
        url = f"{self._host}:{self._port}/api/"
        payload = {"api_key": self._api_key}

        if command == "on":
            url += "start_climate"
            if(self._temperature is not None):
                if self._temperature > DEFAULT_MAX_TEMP:
                    self._temperature = DEFAULT_MAX_TEMP
                if self._temperature < DEFAULT_MIN_TEMP:
                    self._temperature = DEFAULT_MIN_TEMP
            else:
                payload["air_temperature"] = "72"
                _LOGGER.error(f"API call temp is none, setting to default: {self._temperature}")
            #_LOGGER.warning(f"API call temp: {self._temperature}")
            payload["air_temperature"] = str(int(self._temperature))
            #_LOGGER.warning(f"API call after conversion: {payload['air_temperature']}")
        elif command == "off":
            url += "stop_climate"
        # set request as post and data payload as json
        payload = json.dumps(payload)
        #_LOGGER.warning(f"API call payload: {payload}")

        response = requests.post(url, data=payload)
        if response.status_code == 200:
           _LOGGER.info(f"API call successful: {response.text}")
        else:
           _LOGGER.error(f"API call failed: {response.text}")
    # Add methods for HVAC mode if needed