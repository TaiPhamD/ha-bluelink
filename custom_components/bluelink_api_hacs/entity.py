"""Device information and state subscriptions shared by both platforms."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .shared_data import SharedData


class BluelinkEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(self, runtime: SharedData):
        self._runtime = runtime
        vin = runtime.entry.data["selected_vehicle_vin"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            manufacturer="Hyundai",
            name=runtime.entry.data.get("vehicle_name", "Bluelink vehicle"),
        )

    @property
    def available(self):
        return not self._runtime.auth_failed

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.subscribe(self.async_write_ha_state))
