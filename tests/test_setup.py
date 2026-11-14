"""Verify full platform setup and cleanup with Home Assistant."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluelink_api_hacs.bluelink_api import BluelinkAuthError
from custom_components.bluelink_api_hacs.const import DOMAIN


async def test_setup_and_unload(hass, credentials, auth, api):
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
    entities = [
        state
        for state in hass.states.async_all()
        if state.domain in {"climate", "switch"}
    ]
    assert len(entities) == 2
    assert all(state.state == "off" for state in entities)
    await entry.runtime_data.async_set_running(True)
    await hass.async_block_till_done()
    assert {
        state.state
        for state in hass.states.async_all()
        if state.domain in {"climate", "switch"}
    } == {"heat_cool", "on"}
    runtime = entry.runtime_data
    assert runtime._cancel_timer is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert runtime._cancel_timer is None
    assert not runtime._listeners
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
