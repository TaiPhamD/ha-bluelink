"""Verify command state, cooldowns, cleanup, and reauthentication."""

import asyncio
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
def runtime(hass, credentials, api):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TESTVIN",
        data={**credentials, "selected_vehicle_vin": "TESTVIN"},
    )
    entry.add_to_hass(hass)
    return SharedData(hass, entry, api)


async def test_commands_sync_controls_and_persist_tokens(runtime):
    climate = BluelinkClimateControl(runtime)
    switch = BluelinkClimateSwitch(runtime)
    await climate.async_turn_on()
    assert climate.hvac_mode == HVACMode.HEAT_COOL
    assert switch.is_on
    runtime.api.start_climate.assert_called_once_with(72)
    assert runtime.entry.data["auth"] == runtime.api.auth
    runtime.close()


async def test_failed_command_preserves_state(runtime):
    runtime.api.start_climate.side_effect = requests.Timeout()
    with pytest.raises(HomeAssistantError):
        await runtime.async_set_running(True)
    assert not runtime.is_on
    assert runtime._cancel_timer is None


async def test_cooldown_does_not_invent_state(runtime):
    await runtime.async_set_running(True)
    with pytest.raises(ServiceValidationError):
        await runtime.async_set_running(False)
    assert runtime.is_on
    runtime.api.stop_climate.assert_not_called()
    runtime.close()


async def test_concurrent_starts_only_send_one_command(runtime):
    await asyncio.gather(
        runtime.async_set_running(True), runtime.async_set_running(True)
    )
    runtime.api.start_climate.assert_called_once()
    runtime.close()


async def test_auto_off_updates_both_controls(hass, runtime):
    await runtime.async_set_running(True)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=11))
    await hass.async_block_till_done()
    assert not runtime.is_on
    runtime.api.stop_climate.assert_not_called()
    assert runtime._cancel_timer is None


async def test_stop_cancels_timer(runtime):
    await runtime.async_set_running(True)
    with patch(
        "custom_components.bluelink_api_hacs.shared_data.time.monotonic",
        return_value=runtime._last_toggle + 61,
    ):
        await runtime.async_set_running(False)
    assert not runtime.is_on
    assert runtime._cancel_timer is None
    runtime.api.stop_climate.assert_called_once()


async def test_auth_failure_starts_reauth(runtime):
    runtime.api.start_climate.side_effect = BluelinkAuthError()
    with patch.object(type(runtime.entry), "async_start_reauth") as reauth:
        with pytest.raises(HomeAssistantError, match="reauthentication"):
            await runtime.async_set_running(True)
    reauth.assert_called_once_with(runtime.hass)
    assert runtime.auth_failed
    assert not BluelinkClimateSwitch(runtime).available
    assert not runtime.is_on


async def test_vehicle_setpoints_isolated(hass, runtime, credentials, api):
    await runtime.store_data(75)
    entry = MockConfigEntry(domain=DOMAIN, data=credentials)
    other = SharedData(hass, entry, api)
    await other.load_data()
    assert other.temperature == 72
    await other.store_data(68)
    await runtime.load_data()
    assert runtime.temperature == 75


async def test_legacy_setpoint_migration(hass, runtime):
    from homeassistant.helpers.storage import Store

    await Store(hass, 1, "bluelink_climate.json").async_save({"temperature": 74})
    await runtime.load_data()
    assert runtime.temperature == 74


async def test_climate_does_not_report_setpoint_as_cabin_temperature(runtime):
    climate = BluelinkClimateControl(runtime)
    assert climate.current_temperature is None
    assert climate.target_temperature == 72
