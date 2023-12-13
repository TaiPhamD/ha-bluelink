import logging
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import TEMP_FAHRENHEIT, ATTR_TEMPERATURE

from .utils import get_base_host
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up BluelinkClimateControl from a config entry."""
    # Retrieve the existing instance of BluelinkClimateControl from hass.data
    climate_entity = hass.data[DOMAIN][entry.entry_id]["climate"]
    async_add_entities([climate_entity], True)


class BluelinkClimateControl(ClimateEntity):
    def __init__(self, host, port, shared_data):
        self._shared_data = shared_data
        self._temperature = self._shared_data.get_data()
        self._attr_hvac_mode = HVACMode.HEAT_COOL  # Set default to 'auto' mode
        self._attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        # create unique identifier
        base_url = get_base_host(host)
        self._unique_identifier = f"{base_url}_{port}_bluelink_climate"
        self._auto_off_timer = None

    @property
    def supported_features(self):
        return self._attr_supported_features

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
        # return self._temperature
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
            # asyncio.create_task(self._shared_data.store_data(temperature))
            # _LOGGER.warning(f"set_temperature temp: {self._temperature}")
            self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode):
        """Set new target HVAC mode."""
        self._attr_hvac_mode = hvac_mode
        self.schedule_update_ha_state()