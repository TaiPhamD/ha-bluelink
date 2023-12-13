import requests
import logging
import json
from typing import Any
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class Bluelink:
    def __init__(self, host, port, api_key):
        self._api_key = api_key
        self._host = host
        self._port = port

    def set_climate(self, command, temperature=None):
        """Call the Blue Link API with the appropriate command."""
        url = f"{self._host}:{self._port}/api/"
        payload = {"api_key": self._api_key}

        if command == "on":
            payload["air_temperature"] = str(int(temperature))
            # _LOGGER.warning(f"API call after conversion: {payload['air_temperature']}")
            url += "start_climate"
        elif command == "off":
            url += "stop_climate"
        # set request as post and data payload as json
        payload = json.dumps(payload)
        _LOGGER.info(f"bluelink climate: {command}, with temperature: {temperature}")
        _LOGGER.info(f"calling url: {url}")
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            _LOGGER.info(f"bluelink climate: {command}, successful: {response.text}")
        else:
            _LOGGER.error(f"bluelink climate: {command}, failed: {response.text}")