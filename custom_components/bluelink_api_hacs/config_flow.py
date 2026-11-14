"""Set up and repair Bluelink accounts through Home Assistant's UI."""

import logging

import requests
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .bluelink_api import (
    BluelinkAPI,
    BluelinkAuthError,
    BluelinkError,
    BluelinkMFARequired,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

LOGIN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required("pin"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def _authenticate(credentials):
    """Keep session creation and all network I/O off the event loop."""
    api = BluelinkAPI(
        credentials[CONF_USERNAME], credentials[CONF_PASSWORD], credentials["pin"]
    )
    try:
        api.login()
        vehicles = api.get_vehicles(api.get_enrollment_details())
        return api.auth, vehicles
    finally:
        api.close()


class BluelinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """One entry per VIN; reauthentication preserves that vehicle."""

    VERSION = 1

    def __init__(self):
        self._credentials = {}
        self._vehicles = []
        self._entry = None

    async def async_step_user(self, user_input=None):
        return await self._credentials_step("user", user_input)

    async def async_step_reauth(self, entry_data):
        self._entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._credentials_step("reauth_confirm", user_input)

    async def async_step_reconfigure(self, user_input=None):
        self._entry = self._get_reconfigure_entry()
        return await self._credentials_step("reconfigure", user_input)

    async def _credentials_step(self, step_id, user_input):
        errors = {}
        if user_input is not None:
            try:
                auth, self._vehicles = await self.hass.async_add_executor_job(
                    _authenticate, user_input
                )
            except BluelinkMFARequired:
                errors["base"] = "mfa_required"
            except BluelinkAuthError:
                errors["base"] = "invalid_auth"
            except (requests.RequestException, BluelinkError):
                errors["base"] = "cannot_connect"
            except Exception:
                # Do not log API responses, credentials, or token contents.
                _LOGGER.error("Unexpected response while authenticating with Bluelink")
                errors["base"] = "unknown"
            else:
                self._credentials = {**user_input, "auth": auth}
                if not self._vehicles:
                    errors["base"] = "no_vehicles"
                elif self._entry is not None:
                    vin = self._entry.data["selected_vehicle_vin"]
                    vehicle = next((v for v in self._vehicles if v["vin"] == vin), None)
                    if vehicle is None:
                        errors["base"] = "vehicle_not_found"
                    else:
                        await self.async_set_unique_id(vin)
                        self._abort_if_unique_id_mismatch()
                        return self.async_update_reload_and_abort(
                            self._entry,
                            data_updates=self._vehicle_data(vehicle),
                        )
                else:
                    return await self.async_step_select_vehicle()
        schema = LOGIN_DATA_SCHEMA
        if self._entry is not None:
            schema = self.add_suggested_values_to_schema(
                schema, {CONF_USERNAME: self._entry.data[CONF_USERNAME]}
            )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    def _vehicle_data(self, vehicle):
        return self._credentials | {
            "selected_vehicle_vin": vehicle["vin"],
            "selected_vehicle_reg_id": vehicle["reg_id"],
            "vehicle_name": vehicle["nickname"],
            "vehicle_generation": vehicle.get("gen") or "2",
        }

    async def async_step_select_vehicle(self, user_input=None):
        errors = {}
        if user_input is not None:
            vehicle = next(
                (v for v in self._vehicles if v["vin"] == user_input["vehicle"]), None
            )
            if vehicle is not None:
                await self.async_set_unique_id(vehicle["vin"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=vehicle["nickname"], data=self._vehicle_data(vehicle)
                )
            errors["base"] = "invalid_vehicle"
        return self.async_show_form(
            step_id="select_vehicle",
            data_schema=vol.Schema(
                {
                    vol.Required("vehicle"): vol.In(
                        {v["vin"]: v["nickname"] for v in self._vehicles}
                    )
                }
            ),
            errors=errors,
        )
