"""Exercise real HA APIs without depending on the version-pinned pytest harness.

Run with: python -m tests.smoke_latest
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from homeassistant.config_entries import ConfigEntries
from homeassistant.const import __version__
from homeassistant.core import CoreState, HomeAssistant

from custom_components.bluelink_api_hacs import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.bluelink_api_hacs.climate import (
    BluelinkClimateControl,
    HVACMode,
)
from custom_components.bluelink_api_hacs.config_flow import BluelinkConfigFlow
from custom_components.bluelink_api_hacs.const import DOMAIN
from custom_components.bluelink_api_hacs.switch import BluelinkClimateSwitch


async def main():
    with tempfile.TemporaryDirectory() as directory:
        hass = HomeAssistant(str(Path(directory)))
        hass.config_entries = ConfigEntries(hass, {})
        hass.set_state(CoreState.running)
        entry = Mock()
        entry.entry_id = "smoke"
        entry.data = {
            "selected_vehicle_vin": "TESTVIN",
            "selected_vehicle_reg_id": "reg",
            "auth": {"access_token": "test"},
        }
        api = Mock()
        api.auth = entry.data["auth"]
        # Actual setup, storage, subscriptions, command dispatch, and timer cleanup.
        with (
            patch(
                "custom_components.bluelink_api_hacs._create_client", return_value=api
            ),
            patch.object(
                hass.config_entries, "async_forward_entry_setups", return_value=None
            ) as forward,
        ):
            assert await async_setup_entry(hass, entry)
        forward.assert_awaited_once()
        runtime = entry.runtime_data
        climate = BluelinkClimateControl(runtime)
        switch = BluelinkClimateSwitch(runtime)
        climate.hass = switch.hass = hass
        await climate.async_set_temperature(temperature=74)
        await climate.async_turn_on()
        assert switch.is_on
        assert climate.hvac_mode == HVACMode.HEAT_COOL
        assert climate.native_current_temperature is None
        assert climate.native_target_temperature == 74
        api.start_climate.assert_called_once_with(74)
        assert runtime._cancel_timer is not None
        assert climate.device_info["identifiers"] == {(DOMAIN, "TESTVIN")}
        assert hasattr(BluelinkConfigFlow, "async_step_reauth")
        assert hasattr(BluelinkConfigFlow, "async_step_reconfigure")
        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            assert await async_unload_entry(hass, entry)
        assert runtime._cancel_timer is None
        api.close.assert_called_once()
        await hass.async_stop(force=True)
    print(
        f"Home Assistant {__version__}: import, setup, controls, storage, and unload smoke checks passed"
    )


if __name__ == "__main__":
    asyncio.run(main())
