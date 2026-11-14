"""Timestamped vehicle telemetry and remote-command feedback."""

from dataclasses import dataclass
from typing import ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from .entity import BluelinkEntity
from .shared_data import COMMAND_STATES

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class BluelinkSensorDescription(SensorEntityDescription):
    source: str


SENSORS = (
    BluelinkSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        source="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    BluelinkSensorDescription(
        key="vehicle_updated_at",
        translation_key="vehicle_updated_at",
        source="updated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    BluelinkSensorDescription(
        key="reported_target_temperature",
        translation_key="reported_target_temperature",
        source="reported_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = entry.runtime_data
    async_add_entities(
        [
            *(BluelinkTelemetrySensor(runtime, description) for description in SENSORS),
            BluelinkCommandSensor(runtime),
            BluelinkFreshnessSensor(runtime),
            BluelinkCooldownSensor(runtime),
        ]
    )


class BluelinkTelemetrySensor(BluelinkEntity, SensorEntity):
    entity_description: BluelinkSensorDescription

    def __init__(self, runtime, description):
        super().__init__(runtime)
        self.entity_description = description
        self._attr_unique_id = (
            f"{runtime.entry.data['selected_vehicle_vin']}_{description.key}"
        )

    @property
    def native_value(self):
        status = self._runtime.status
        return getattr(status, self.entity_description.source) if status else None


class BluelinkCommandSensor(BluelinkEntity, SensorEntity):
    _attr_translation_key = "command_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = COMMAND_STATES
    _attr_icon = "mdi:car-connected"

    def __init__(self, runtime):
        super().__init__(runtime)
        self._attr_unique_id = (
            f"{runtime.entry.data['selected_vehicle_vin']}_command_status"
        )

    @property
    def available(self):
        # Keep the explanation visible when authentication disables the controls.
        return True

    @property
    def native_value(self):
        return self._runtime.command_status

    @property
    def extra_state_attributes(self):
        runtime = self._runtime
        return super().extra_state_attributes | {
            "action": runtime.command_action,
            "started_at": runtime.command_started_at,
            "finished_at": runtime.command_finished_at,
            "error": runtime.command_error,
            "in_progress": runtime.busy,
        }


class BluelinkFreshnessSensor(BluelinkEntity, SensorEntity):
    _attr_translation_key = "vehicle_feedback"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options: ClassVar[list[str]] = ["current", "stale", "never_received"]
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, runtime):
        super().__init__(runtime)
        self._attr_unique_id = (
            f"{runtime.entry.data['selected_vehicle_vin']}_vehicle_feedback"
        )

    @property
    def native_value(self):
        if self._runtime.status is None:
            return "never_received"
        return "stale" if self._runtime.is_stale else "current"


class BluelinkCooldownSensor(BluelinkEntity, SensorEntity):
    _attr_translation_key = "next_command_available"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-sand"

    def __init__(self, runtime):
        super().__init__(runtime)
        self._attr_unique_id = (
            f"{runtime.entry.data['selected_vehicle_vin']}_next_command_available"
        )

    @property
    def native_value(self):
        return self._runtime.cooldown_until
