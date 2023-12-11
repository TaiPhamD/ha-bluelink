import logging
import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Required("api_key"): cv.string,
    vol.Required("air_temperature", default=72): cv.positive_int,
})

class BluelinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Bluelink config flow."""

    VERSION = 1  # Increment this when changes are made to the config flow

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Here you can add additional validation if needed
            return self.async_create_entry(title="Bluelink Integration", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
