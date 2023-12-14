import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .bluelink_api import BluelinkAPI

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required("pin"): cv.string,
    }
)

class BluelinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    vehicles = None  # Store vehicles data
    user_input_data = None  # Store user input data from the first step

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            self.user_input_data = user_input  # Store user input for later use
            bluelink_api = BluelinkAPI(
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                pin=user_input["pin"],
            )
            try:
                await self.hass.async_add_executor_job(bluelink_api.login)
                details = await self.hass.async_add_executor_job(bluelink_api.get_enrollment_details)
                self.vehicles = bluelink_api.get_vehicles(details)

                # Proceed to vehicle selection step
                return await self.async_step_select_vehicle()

            except Exception as e:
                _LOGGER.error(f"Error connecting to Bluelink API: {e}")
                errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    async def async_step_select_vehicle(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Find the vehicle corresponding to the selected VIN
            selected_vehicle = next((v for v in self.vehicles if v["vin"] == user_input["vehicle"]), None)

            if selected_vehicle:
                # Combine user input data with selected vehicle data
                config_data = {
                    **self.user_input_data,
                    "selected_vehicle_vin": selected_vehicle["vin"],
                    "selected_vehicle_reg_id": selected_vehicle["reg_id"]
                }
                return self.async_create_entry(title="Bluelink Integration", data=config_data)

            errors["base"] = "invalid_vehicle"

        vehicles_options = {v["vin"]: v["nickname"] for v in self.vehicles}
        return self.async_show_form(
            step_id="select_vehicle",
            data_schema=vol.Schema({
                vol.Required("vehicle", default=list(vehicles_options.keys())[0]): vol.In(vehicles_options)
            }),
            errors=errors
        )
