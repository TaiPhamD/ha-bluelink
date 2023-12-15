import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .bluelink_api import BluelinkAPI

_LOGGER = logging.getLogger(__name__)

LOGIN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required("pin"): cv.string,
    }
)


class BluelinkFlowBase:
    async def async_step_select_vehicle(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Find the vehicle corresponding to the selected VIN
            selected_vehicle = next(
                (v for v in self.vehicles if v["vin"] == user_input["vehicle"]), None
            )

            if selected_vehicle:
                # Combine user input data with selected vehicle data
                config_data = {
                    **self.user_input_data,
                    "selected_vehicle_vin": selected_vehicle["vin"],
                    "selected_vehicle_reg_id": selected_vehicle["reg_id"],
                }
                if self.check_unique is True:
                    # Check if a configuration entry for this VIN already exists
                    errors["base"] = "already_configured"
                    await self.async_set_unique_id(selected_vehicle["vin"])
                    self._abort_if_unique_id_configured()
                    errors = {}

                return self.async_create_entry(
                    title="Bluelink Integration", data=config_data
                )

            errors["base"] = "invalid_vehicle"

        vehicles_options = {v["vin"]: v["nickname"] for v in self.vehicles}
        return self.async_show_form(
            step_id="select_vehicle",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "vehicle", default=list(vehicles_options.keys())[0]
                    ): vol.In(vehicles_options)
                }
            ),
            errors=errors,
        )

    async def handle_login_and_vehicle_selection(self, user_input, step_id):
        """Handle the login and vehicle selection process."""
        errors = {}
        bluelink_api = BluelinkAPI(
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            pin=user_input["pin"],
        )

        try:
            auth = await self.hass.async_add_executor_job(bluelink_api.login)
            details = await self.hass.async_add_executor_job(
                bluelink_api.get_enrollment_details
            )
            self.vehicles = bluelink_api.get_vehicles(details)
            self.user_input_data = {**user_input, "auth": auth}
            return await self.async_step_select_vehicle(user_input=None)
        except Exception as e:
            _LOGGER.error(f"Error connecting to Bluelink API: {e}")
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id=step_id, data_schema=LOGIN_DATA_SCHEMA, errors=errors
            )


class BluelinkOptionsFlowHandler(BluelinkFlowBase, config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.vehicles = []  # Initialize vehicles
        self.user_input_data = {**config_entry.data}  # Initialize with existing config
        self.check_unique = False

    async def async_step_init(self, user_input=None):
        """Handle the initial step in the options flow."""
        if user_input is not None:
            # we are updating an existing entity so set initial=false
            result = await self.handle_login_and_vehicle_selection(
                user_input, step_id="init"
            )
            # Check if the flow has completed successfully
            if result.get("type") == "create_entry":
                # Update the configuration entry with the new data
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.user_input_data, **user_input}
                )

                # Unload and reload the integration to apply the new configuration
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_abort(reason="options_updated")

            return result

        # If there's no user input, show the initial form
        return self.async_show_form(
            step_id="init",
            data_schema=LOGIN_DATA_SCHEMA,  # Adjust this schema as per your options
        )


class BluelinkConfigFlow(BluelinkFlowBase, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.vehicles = None  # Store vehicles data
        self.user_input_data = None  # Store user input data from the first step
        self.check_unique = True  # Default value for check_unique

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.check_unique = True
            return await self.handle_login_and_vehicle_selection(
                user_input, step_id="user"
            )
        return self.async_show_form(step_id="user", data_schema=LOGIN_DATA_SCHEMA)

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return BluelinkOptionsFlowHandler(config_entry)
