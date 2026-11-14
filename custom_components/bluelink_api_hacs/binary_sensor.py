"""Hyundai-reported charging and defrost state."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .entity import BluelinkEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            BluelinkBinarySensor(
                entry.runtime_data, "charging", BinarySensorDeviceClass.BATTERY_CHARGING
            ),
            BluelinkBinarySensor(entry.runtime_data, "defrost_on", None),
        ]
    )


class BluelinkBinarySensor(BluelinkEntity, BinarySensorEntity):
    def __init__(self, runtime, key, device_class):
        super().__init__(runtime)
        self._key = key
        self._attr_translation_key = key
        self._attr_device_class = device_class
        if key == "defrost_on":
            self._attr_icon = "mdi:car-defrost-front"
        self._attr_unique_id = f"{runtime.entry.data['selected_vehicle_vin']}_{key}"

    @property
    def is_on(self):
        status = self._runtime.status
        return getattr(status, self._key) if status else None
