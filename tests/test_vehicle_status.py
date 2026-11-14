"""Missing fields, timestamp formats, and HVAC setpoints are handled honestly."""

from datetime import UTC, datetime

import pytest

from custom_components.bluelink_api_hacs.vehicle_status import VehicleStatus


@pytest.mark.parametrize(
    "date", ["20261114123000", "2026-11-14T12:30:00Z", "2026-11-14T04:30:00-08:00"]
)
def test_timestamp_formats(date):
    status = VehicleStatus.from_response({"dateTime": date})
    assert status.updated_at == datetime(2026, 11, 14, 12, 30, tzinfo=UTC)


def test_parse_vehicle_feedback():
    status = VehicleStatus.from_response(
        {
            "airCtrlOn": "true",
            "defrost": 0,
            "evStatus": {"batteryStatus": "78", "batteryCharge": "1"},
            "airTemp": {"value": "72", "unit": 1},
        }
    )
    assert status.climate_on is True
    assert status.defrost_on is False
    assert status.battery_level == 78
    assert status.charging is True
    assert status.reported_temperature == 72


def test_missing_feedback_is_unknown():
    status = VehicleStatus.from_response({})
    assert all(value is None for value in status.__dict__.values())


@pytest.mark.parametrize(
    "date", [None, "bad", "20261314123000", "2026-11-14T12:30:00", 20261114123000]
)
def test_ambiguous_timestamp_is_unknown(date):
    assert VehicleStatus.from_response({"dateTime": date}).updated_at is None


@pytest.mark.parametrize("battery", ["bad", "nan", -1, 101, True])
def test_invalid_battery_is_unknown(battery):
    assert (
        VehicleStatus.from_response(
            {"evStatus": {"batteryStatus": battery}}
        ).battery_level
        is None
    )


@pytest.mark.parametrize("temperature", ["LO", "HI", "OFF", None, "0x0F"])
def test_unknown_temperature_is_not_guessed(temperature):
    assert (
        VehicleStatus.from_response(
            {"airTemp": {"value": temperature, "unit": 1}}
        ).reported_temperature
        is None
    )
