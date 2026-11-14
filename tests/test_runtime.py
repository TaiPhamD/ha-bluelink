"""Verify reported state, command feedback, refreshes, and cleanup."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

import pytest
import requests
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.bluelink_api_hacs.bluelink_api import BluelinkAuthError
from custom_components.bluelink_api_hacs.climate import BluelinkClimateControl, HVACMode
from custom_components.bluelink_api_hacs.const import DOMAIN
from custom_components.bluelink_api_hacs.shared_data import SharedData
from custom_components.bluelink_api_hacs.switch import BluelinkClimateSwitch


@pytest.fixture
async def runtime(hass, credentials, api, status, monkeypatch):
    monkeypatch.setattr(
        "custom_components.bluelink_api_hacs.shared_data.COMMAND_POLL_INTERVAL", 0
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TESTVIN",
        data={**credentials, "selected_vehicle_vin": "TESTVIN"},
    )
    entry.add_to_hass(hass)
    runtime = SharedData(hass, entry, api)
    runtime.coordinator.async_set_updated_data(status)
    yield runtime
    await runtime.async_close()


async def monitor_now(runtime):
    with patch(
        "custom_components.bluelink_api_hacs.shared_data.COMMAND_POLL_INTERVAL", 0
    ):
        await runtime._monitor_task


async def test_acceptance_is_not_vehicle_confirmation(runtime):
    climate = BluelinkClimateControl(runtime)
    switch = BluelinkClimateSwitch(runtime)
    await climate.async_turn_on()
    assert climate.hvac_mode == HVACMode.OFF
    assert switch.is_on is False
    assert runtime.command_status in {"accepted", "pending"}
    assert runtime.entry.data["auth"] == runtime.api.auth
    assert runtime.cooldown_until is not None


async def test_command_completion_and_fresh_telemetry(runtime, status):
    runtime.api.get_vehicle_status.return_value = replace(
        status, climate_on=True, updated_at=dt_util.utcnow()
    )
    await runtime.async_set_running(True)
    await monitor_now(runtime)
    assert runtime.command_status == "succeeded"
    assert runtime.command_finished_at is not None
    assert runtime.is_on is True
    runtime.api.check_action_status.assert_called_once_with("transaction")


async def test_success_does_not_rewrite_old_vehicle_snapshot(runtime):
    await runtime.async_set_running(True)
    await monitor_now(runtime)
    assert runtime.command_status == "succeeded"
    assert runtime.is_on is False


async def test_failed_completion_preserves_vehicle_state(runtime):
    runtime.api.check_action_status.return_value = "failed"
    await runtime.async_set_running(True)
    await monitor_now(runtime)
    assert runtime.command_status == "failed"
    assert runtime.command_error
    assert runtime.is_on is False


async def test_timeout_never_claims_car_started(runtime):
    runtime.api.check_action_status.return_value = "pending"
    with patch("custom_components.bluelink_api_hacs.shared_data.COMMAND_TIMEOUT", 0):
        await runtime.async_set_running(True)
        await runtime._monitor_task
    assert runtime.command_status == "timed_out"
    assert runtime.is_on is False


async def test_no_tracking_id_is_unconfirmed(runtime):
    runtime.api.start_climate.return_value = None
    await runtime.async_set_running(True)
    await runtime._monitor_task
    assert runtime.command_status == "unconfirmed"
    assert runtime.is_on is False
    runtime.api.check_action_status.assert_not_called()


async def test_failed_request_stays_unconfirmed_and_has_cooldown(runtime):
    runtime.api.start_climate.side_effect = requests.Timeout()
    with pytest.raises(HomeAssistantError):
        await runtime.async_set_running(True)
    assert runtime.command_status == "unconfirmed"
    assert runtime.is_on is False
    with pytest.raises(ServiceValidationError):
        await runtime.async_set_running(True)
    assert runtime.api.start_climate.call_count == 1


async def test_opposite_command_blocked_while_pending(runtime):
    await runtime.async_set_running(True)
    with pytest.raises(ServiceValidationError):
        await runtime.async_set_running(False)
    runtime.api.stop_climate.assert_not_called()


async def test_concurrent_starts_only_send_one_command(runtime):
    await asyncio.gather(
        runtime.async_set_running(True), runtime.async_set_running(True)
    )
    runtime.api.start_climate.assert_called_once()


async def test_cooldown_clears_without_inventing_auto_off(hass, runtime, status):
    runtime.coordinator.async_set_updated_data(replace(status, climate_on=True))
    runtime.api.stop_climate.return_value = None
    runtime.api.get_vehicle_status.return_value = replace(status, climate_on=True)
    await runtime.async_set_running(False)
    await runtime._monitor_task
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=11))
    await hass.async_block_till_done()
    assert runtime.cooldown_until is None
    assert runtime.is_on is True
    runtime.api.stop_climate.assert_called_once()


async def test_auth_failure_starts_reauth_once(runtime):
    runtime.api.start_climate.side_effect = BluelinkAuthError()
    with patch.object(type(runtime.entry), "async_start_reauth") as reauth:
        for _ in range(2):
            with pytest.raises(HomeAssistantError, match="reauthentication"):
                await runtime.async_set_running(True)
    reauth.assert_called_once_with(runtime.hass)
    assert runtime.command_status == "authentication_required"
    assert not BluelinkClimateSwitch(runtime).available


async def test_older_snapshot_cannot_replace_newer(runtime, status):
    runtime.api.get_vehicle_status.return_value = replace(
        status, climate_on=True, updated_at=status.updated_at - timedelta(hours=1)
    )
    await runtime.coordinator.async_refresh()
    assert runtime.is_on is False
    assert runtime.status.updated_at == status.updated_at


async def test_refresh_failure_retains_snapshot_and_marks_stale(runtime):
    runtime.api.get_vehicle_status.side_effect = requests.Timeout()
    await runtime.coordinator.async_refresh()
    assert runtime.is_on is False
    assert runtime.is_stale
    assert not runtime.coordinator.last_update_success


async def test_missing_feedback_does_not_prevent_start(runtime):
    runtime.coordinator.async_set_updated_data(None)
    assert runtime.is_on is None
    assert BluelinkClimateControl(runtime).hvac_mode is None
    await runtime.async_set_running(True)
    runtime.api.start_climate.assert_called_once()


async def test_force_refresh_is_explicit_and_limited(runtime):
    await runtime.async_refresh_status(force=True)
    runtime.api.get_vehicle_status.assert_called_once_with(True)
    with pytest.raises(ServiceValidationError):
        await runtime.async_refresh_status(force=True)


async def test_cached_refresh_does_not_wake_car(runtime):
    await runtime.coordinator.async_refresh()
    runtime.api.get_vehicle_status.assert_called_once_with()


async def test_vehicle_setpoints_isolated(hass, runtime, credentials, api):
    await runtime.store_data(75)
    entry = MockConfigEntry(domain=DOMAIN, data=credentials)
    other = SharedData(hass, entry, api)
    await other.load_data()
    assert other.temperature == 72
    await other.store_data(68)
    await runtime.load_data()
    assert runtime.temperature == 75
    await other.coordinator.async_shutdown()


async def test_legacy_setpoint_migration(hass, runtime):
    from homeassistant.helpers.storage import Store

    await Store(hass, 1, "bluelink_climate.json").async_save({"temperature": 74})
    await runtime.load_data()
    assert runtime.temperature == 74


async def test_setpoint_and_cabin_temperature_are_distinct(runtime):
    climate = BluelinkClimateControl(runtime)
    await climate.async_set_temperature(temperature=76)
    assert climate.current_temperature is None
    assert climate.target_temperature == 76
    assert climate.extra_state_attributes["reported_target_temperature"] == 72
    assert climate.extra_state_attributes["temperature_applies_to"] == "next_start"
    runtime.api.start_climate.assert_not_called()


async def test_feedback_checks_stop_once_matching_snapshot_arrives(runtime, status):
    await runtime.async_set_running(True)
    await monitor_now(runtime)
    runtime.api.get_vehicle_status.reset_mock()
    await runtime._async_refresh_feedback(None)
    runtime.api.get_vehicle_status.assert_called_once_with()
    runtime.coordinator.async_set_updated_data(
        replace(
            status,
            climate_on=True,
            updated_at=runtime.command_started_at + timedelta(seconds=1),
        )
    )
    runtime.api.get_vehicle_status.reset_mock()
    await runtime._async_refresh_feedback(None)
    runtime.api.get_vehicle_status.assert_not_called()


async def test_cancellation_waits_for_inflight_request_before_close(runtime):
    import threading

    started = asyncio.Event()
    loop = asyncio.get_running_loop()
    release = threading.Event()

    def blocking_request(_temperature):
        loop.call_soon_threadsafe(started.set)
        release.wait(3)
        return "transaction"

    runtime.api.start_climate = blocking_request
    task = asyncio.create_task(runtime.async_set_running(True))
    await started.wait()
    task.cancel()
    close_task = asyncio.create_task(runtime.async_close())
    await asyncio.sleep(0)
    runtime.api.close.assert_not_called()
    release.set()
    await asyncio.gather(task, return_exceptions=True)
    await close_task
    runtime.api.close.assert_called_once()


async def test_concurrent_force_refreshes_are_limited(runtime):
    results = await asyncio.gather(
        runtime.async_refresh_status(True),
        runtime.async_refresh_status(True),
        return_exceptions=True,
    )
    assert sum(isinstance(result, ServiceValidationError) for result in results) == 1
    runtime.api.get_vehicle_status.assert_called_once_with(True)


async def test_periodic_fetch_uses_cache_and_stops_on_unload(hass, runtime):
    from homeassistant.core import CoreState

    hass.set_state(CoreState.running)
    await runtime.async_initialize()
    runtime.api.get_vehicle_status.reset_mock()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done()
    runtime.api.get_vehicle_status.assert_called_once_with()
    runtime.close()
    await runtime.coordinator.async_shutdown()
    runtime.api.get_vehicle_status.reset_mock()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=12))
    await hass.async_block_till_done()
    runtime.api.get_vehicle_status.assert_not_called()
