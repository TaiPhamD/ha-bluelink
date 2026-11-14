"""Verify full platform setup and cleanup with Home Assistant."""

from dataclasses import replace
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluelink_api_hacs.bluelink_api import BluelinkAuthError
from custom_components.bluelink_api_hacs.const import DOMAIN


async def test_setup_and_unload(hass, credentials, auth, api, status):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TESTVIN",
        data={
            **credentials,
            "auth": auth,
            "selected_vehicle_vin": "TESTVIN",
            "selected_vehicle_reg_id": "reg",
            "vehicle_name": "IONIQ 5",
        },
    )
    entry.add_to_hass(hass)
    with patch("custom_components.bluelink_api_hacs._create_client", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED
    for domain, count in [("sensor", 6), ("binary_sensor", 2), ("button", 2)]:
        assert (
            len([state for state in hass.states.async_all() if state.domain == domain])
            == count
        )
    entities = [
        state
        for state in hass.states.async_all()
        if state.domain in {"climate", "switch"}
    ]
    assert len(entities) == 2
    assert all(state.state == "off" for state in entities)
    await entry.runtime_data.async_set_running(True)
    assert entry.runtime_data.is_on is False
    api.get_vehicle_status.return_value = replace(status, climate_on=True)
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert {
        state.state
        for state in hass.states.async_all()
        if state.domain in {"climate", "switch"}
    } == {"heat_cool", "on"}
    runtime = entry.runtime_data
    assert runtime._cooldown_cancel is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert runtime._cooldown_cancel is None
    assert not runtime._listeners
    assert not runtime._feedback_cancels
    assert runtime._monitor_task.done()
    api.close.assert_called_once()


async def test_setup_auth_failure_starts_reauth(hass, credentials, api):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="TESTVIN", data=credentials)
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.bluelink_api_hacs._create_client",
            side_effect=BluelinkAuthError(),
        ),
        patch.object(type(entry), "async_start_reauth") as reauth,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR
    reauth.assert_called_once()


async def test_missing_telemetry_still_loads_controls(hass, credentials, auth, api):
    import requests

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TESTVIN",
        data={
            **credentials,
            "auth": auth,
            "selected_vehicle_vin": "TESTVIN",
            "selected_vehicle_reg_id": "reg",
        },
    )
    entry.add_to_hass(hass)
    api.get_vehicle_status.side_effect = requests.Timeout()
    with patch("custom_components.bluelink_api_hacs._create_client", return_value=api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    climate_states = [
        state for state in hass.states.async_all() if state.domain == "climate"
    ]
    assert len(climate_states) == 1
    assert climate_states[0].state == "unknown"
    assert await hass.config_entries.async_unload(entry.entry_id)
