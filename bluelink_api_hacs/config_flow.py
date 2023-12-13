import logging
import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .bluelink_api import BluelinkAPI

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME, default="user@domain.com"): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_PIN): cv.string,
    vol.Required("vin","KMXXXXXXXXXXXXXXX"): cv.string,
})

class BluelinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Bluelink config flow."""
    VERSION = 1  # Increment this when changes are made to the config flow

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Create an instance of BluelinkAPI with the provided credentials
            bluelink_api = BluelinkAPI(
                username=user_input["username"],
                password=user_input["password"],
                pin=user_input["pin"],
                vin=user_input["vin"]
            )
            # Perform login test
            try:
                auth = bluelink_api._login()  # Using _login method to test credentials

                if auth is None:
                    errors["base"] = "invalid_auth"
                elif 'reg_id' not in auth or auth['reg_id'] is None:
                    errors["base"] = "invalid_vin"
                else:
                    return self.async_create_entry(title="Bluelink Integration", data=user_input)
            except Exception as e:
                _LOGGER.error(f"Error connecting to Bluelink API: {e}")
                errors["base"] = "cannot_connect"            

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
