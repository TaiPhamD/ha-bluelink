"""Test setup and reauthentication through Home Assistant's flow manager."""

from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bluelink_api_hacs.bluelink_api import BluelinkAuthError
from custom_components.bluelink_api_hacs.const import DOMAIN

AUTHENTICATE = "custom_components.bluelink_api_hacs.config_flow._authenticate"


async def test_user_select_vehicle(hass, credentials, auth, vehicle):
    with (
        patch(AUTHENTICATE, return_value=(auth, [vehicle])),
        patch(
            "custom_components.bluelink_api_hacs.async_setup_entry", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=credentials
        )
        assert result["step_id"] == "select_vehicle"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"vehicle": vehicle["vin"]}
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == vehicle["vin"]
    assert result["data"]["pin"] == "0123"


async def test_no_enrolled_vehicles(hass, credentials, auth):
    with patch(AUTHENTICATE, return_value=(auth, [])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=credentials
        )
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_vehicles"}


async def test_invalid_credentials(hass, credentials):
    with patch(AUTHENTICATE, side_effect=BluelinkAuthError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=credentials
        )
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize(
    "source,step",
    [(SOURCE_REAUTH, "reauth_confirm"), (SOURCE_RECONFIGURE, "reconfigure")],
)
async def test_update_existing_vehicle(hass, credentials, auth, vehicle, source, step):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=vehicle["vin"],
        data={
            **credentials,
            "auth": {"access_token": "old"},
            "selected_vehicle_vin": vehicle["vin"],
            "selected_vehicle_reg_id": "old-reg",
        },
    )
    entry.add_to_hass(hass)
    with (
        patch(AUTHENTICATE, return_value=(auth, [vehicle])),
        patch.object(hass.config_entries, "async_schedule_reload") as reload_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source, "entry_id": entry.entry_id},
            data=entry.data if source == SOURCE_REAUTH else None,
        )
        assert result["step_id"] == step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**credentials, "password": "changed"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert entry.data["auth"] == auth
    assert entry.data["password"] == "changed"
    assert entry.data["selected_vehicle_reg_id"] == vehicle["reg_id"]
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    reload_entry.assert_called_once_with(entry.entry_id)


async def test_reauth_cannot_switch_vehicle(hass, credentials, auth, vehicle):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="OTHER",
        data={**credentials, "selected_vehicle_vin": "OTHER"},
    )
    entry.add_to_hass(hass)
    with patch(AUTHENTICATE, return_value=(auth, [vehicle])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], credentials
        )
    assert result["errors"] == {"base": "vehicle_not_found"}
    assert "auth" not in entry.data
