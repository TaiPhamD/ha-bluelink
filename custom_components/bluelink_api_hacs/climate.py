"""Bluelink remote climate control."""

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import ServiceValidationError

from .entity import BluelinkEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([BluelinkClimateControl(entry.runtime_data)])


class BluelinkClimateControl(BluelinkEntity, ClimateEntity):
    _attr_translation_key = "climate"
    _attr_native_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = 62
    _attr_max_temp = 82
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, runtime):
        super().__init__(runtime)
        # Preserve existing registry IDs and automations.
        self._attr_unique_id = (
            f"{runtime.entry.data['selected_vehicle_vin']}_bluelink_climate"
        )

    @property
    def hvac_mode(self):
        if self._runtime.is_on is None:
            return None
        return HVACMode.HEAT_COOL if self._runtime.is_on else HVACMode.OFF

    @property
    def assumed_state(self):
        return self._runtime.is_stale

    @property
    def extra_state_attributes(self):
        runtime = self._runtime
        return super().extra_state_attributes | {
            "command_status": runtime.command_status,
            "command_in_progress": runtime.busy,
            "command_error": runtime.command_error,
            "next_command_available": runtime.cooldown_until,
            "temperature_applies_to": "next_start",
            "reported_target_temperature": runtime.status.reported_temperature
            if runtime.status
            else None,
        }

    @property
    def native_target_temperature(self):
        return self._runtime.temperature

    # Define legacy names only on Home Assistant versions before 2026.11.
    if not hasattr(ClimateEntity, "native_target_temperature"):
        _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        target_temperature = native_target_temperature

    async def async_set_temperature(self, **kwargs: Any):
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            if not self.min_temp <= temperature <= self.max_temp:
                raise ServiceValidationError("Temperature must be between 62 and 82 °F")
            await self._runtime.store_data(temperature)
        if ATTR_HVAC_MODE in kwargs:
            await self.async_set_hvac_mode(kwargs[ATTR_HVAC_MODE])

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode not in self.hvac_modes:
            raise ServiceValidationError("Unsupported Bluelink HVAC mode")
        await self._runtime.async_set_running(hvac_mode != HVACMode.OFF)

    async def async_turn_on(self):
        await self._runtime.async_set_running(True)

    async def async_turn_off(self):
        await self._runtime.async_set_running(False)
