import logging
import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv

import ssl
import socket
from urllib.parse import urlparse


from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST, default="https://your_domain.com"): cv.string,
    vol.Required(CONF_PORT, default=443): cv.port,
    vol.Required("api_key", default="xxxxxxx"): cv.string,
})

def is_valid_ssl_cert(host, port):
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    try:
        conn = ctx.wrap_socket(socket.socket(socket.AF_INET), server_hostname=host)
        conn.connect((host, port))
        conn.close()
        return True
    except ssl.SSLCertVerificationError:
        return False
    except Exception as e:
        _LOGGER.warning(f"SSL certificate validation error: {e}")
        return False


class BluelinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Bluelink config flow."""

    VERSION = 1  # Increment this when changes are made to the config flow

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            raw_host = user_input[CONF_HOST]
            parsed_host = urlparse(raw_host).hostname        
            host = urlparse(user_input[CONF_HOST]).hostname
            port = user_input.get(CONF_PORT, 443)  # Default to port 443 for HTTPS if not provided
            if not is_valid_ssl_cert(host, port):
                errors["base"] = "invalid_ssl_certificate"
                _LOGGER.warning(f"SSL certificate validation host: {host}, port: {port}")
            else:
                # Additional validation if needed
                return self.async_create_entry(title="Bluelink Integration", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
