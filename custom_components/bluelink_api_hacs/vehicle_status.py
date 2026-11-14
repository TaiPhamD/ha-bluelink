"""Parse only the vehicle feedback we display; never retain raw account data."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from homeassistant.util import dt as dt_util


def _boolean(value):
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True"):
        return True
    if value in (0, "0", "false", "False"):
        return False
    return None


def _number(value, minimum, maximum):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and minimum <= number <= maximum else None


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        if len(value) == 14 and value.isdecimal():
            return datetime.strptime(value, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        parsed = dt_util.parse_datetime(value)
        if parsed is not None and parsed.tzinfo is not None:
            return dt_util.as_utc(parsed)
    except ValueError:
        pass
    return None


@dataclass(frozen=True)
class VehicleStatus:
    """A Hyundai snapshot, which may be older than the time we fetched it."""

    climate_on: bool | None
    defrost_on: bool | None
    battery_level: float | None
    charging: bool | None
    updated_at: datetime | None
    reported_temperature: float | None

    @classmethod
    def from_response(cls, status):
        ev = status.get("evStatus")
        ev = ev if isinstance(ev, dict) else {}
        air = status.get("airTemp")
        air = air if isinstance(air, dict) else {}
        # This is the HVAC setpoint, not a cabin temperature measurement.
        temperature = (
            _number(air.get("value"), 32, 100) if str(air.get("unit")) == "1" else None
        )
        return cls(
            climate_on=_boolean(status.get("airCtrlOn")),
            defrost_on=_boolean(status.get("defrost")),
            battery_level=_number(ev.get("batteryStatus"), 0, 100),
            charging=_boolean(ev.get("batteryCharge")),
            updated_at=_timestamp(status.get("dateTime")),
            reported_temperature=temperature,
        )
