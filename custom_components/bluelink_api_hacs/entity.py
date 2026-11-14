"""Device information and state subscriptions shared by both platforms."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .shared_data import SharedData


class BluelinkEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

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

    @property
    def extra_state_attributes(self):
        runtime = self._runtime
        status = runtime.status
        return {
            "vehicle_updated_at": status.updated_at if status else None,
            "status_received_at": runtime.last_received_at,
            "vehicle_data_stale": runtime.is_stale,
            "status_fetch_success": runtime.coordinator.last_update_success,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.subscribe(self.async_write_ha_state))
