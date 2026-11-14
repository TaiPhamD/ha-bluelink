"""Separate cache reads from requests that contact the vehicle."""

from homeassistant.components.button import ButtonEntity

from .entity import BluelinkEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            BluelinkRefreshButton(entry.runtime_data, False),
            BluelinkRefreshButton(entry.runtime_data, True),
        ]
    )


class BluelinkRefreshButton(BluelinkEntity, ButtonEntity):
    _attr_icon = "mdi:refresh"

    def __init__(self, runtime, force):
        super().__init__(runtime)
        self._force = force
        key = "request_vehicle_update" if force else "refresh_cached_status"
        self._attr_translation_key = key
        self._attr_unique_id = f"{runtime.entry.data['selected_vehicle_vin']}_{key}"

    async def async_press(self):
        await self._runtime.async_refresh_status(self._force)
