"""Compatibility switch for Bluelink remote climate control."""

from homeassistant.components.switch import SwitchEntity

from .entity import BluelinkEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([BluelinkClimateSwitch(entry.runtime_data)])


class BluelinkClimateSwitch(BluelinkEntity, SwitchEntity):
    _attr_translation_key = "climate_switch"
    _attr_icon = "mdi:car-defrost-front"

    def __init__(self, runtime):
        super().__init__(runtime)
        self._attr_unique_id = (
            f"{runtime.entry.data['selected_vehicle_vin']}_bluelink_switch"
        )

    @property
    def is_on(self):
        return self._runtime.is_on

    async def async_turn_on(self, **kwargs):
        await self._runtime.async_set_running(True)

    async def async_turn_off(self, **kwargs):
        await self._runtime.async_set_running(False)
