"""Shared runtime state for a vehicle's climate and switch entities."""

import asyncio
import time
from collections.abc import Callable

import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .bluelink_api import BluelinkAPI, BluelinkAuthError, BluelinkError
from .const import BLUELINK_CLIMATE_MAX_TIMER, BLUELINK_SWITCH_TOGGLE_TIMEOUT, DOMAIN


class SharedData:
    """Serialize commands and keep both controls in sync without polling the car."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: BluelinkAPI):
        self.hass = hass
        self.entry = entry
        self.api = api
        self.storage = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.temperature = 72
        self.is_on = False
        self._lock = asyncio.Lock()
        self._listeners: set[Callable] = set()
        self._cancel_timer = None
        self._last_toggle: float | None = None
        self.auth_failed = False

    async def load_data(self):
        data = await self.storage.async_load()
        migrated = data is None
        if data is None:
            # Copy the old shared setpoint once, then save per vehicle.
            data = await Store(self.hass, 1, "bluelink_climate.json").async_load()
        if (
            data
            and isinstance(value := data.get("temperature"), (int, float))
            and 62 <= value <= 82
        ):
            self.temperature = value
            if migrated:
                await self.storage.async_save({"temperature": value})

    async def store_data(self, temperature):
        self.temperature = temperature
        await self.storage.async_save({"temperature": temperature})
        self._notify()

    def get_data(self):
        return self.temperature

    @callback
    def subscribe(self, listener):
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    @callback
    def _notify(self):
        for listener in tuple(self._listeners):
            listener()

    @callback
    def save_auth(self):
        auth = self.api.auth
        if auth != self.entry.data.get("auth"):
            self.hass.config_entries.async_update_entry(
                self.entry, data={**self.entry.data, "auth": auth}
            )

    async def async_set_running(self, running: bool):
        async with self._lock:
            if self.auth_failed:
                raise HomeAssistantError(
                    "Bluelink needs reauthentication in Settings > Devices & services"
                )
            if running == self.is_on:
                return
            if (
                self._last_toggle is not None
                and time.monotonic() - self._last_toggle
                < BLUELINK_SWITCH_TOGGLE_TIMEOUT
            ):
                raise ServiceValidationError(
                    "Wait 60 seconds between Bluelink climate commands"
                )
            try:
                if running:
                    await self.hass.async_add_executor_job(
                        self.api.start_climate, self.temperature
                    )
                else:
                    await self.hass.async_add_executor_job(self.api.stop_climate)
            except BluelinkAuthError as err:
                self.auth_failed = True
                self.entry.async_start_reauth(self.hass)
                self._notify()
                raise HomeAssistantError(
                    "Bluelink needs reauthentication in Settings > Devices & services"
                ) from err
            except (requests.RequestException, BluelinkError) as err:
                raise HomeAssistantError(
                    "Hyundai could not accept the climate command"
                ) from err
            finally:
                self.save_auth()
            self._last_toggle = time.monotonic()
            self.is_on = running
            self._cancel_auto_off()
            if running:
                self._cancel_timer = async_call_later(
                    self.hass, BLUELINK_CLIMATE_MAX_TIMER, self._auto_off
                )
            self._notify()

    @callback
    def _auto_off(self, _now):
        self._cancel_timer = None
        self.is_on = False
        self._notify()

    @callback
    def _cancel_auto_off(self):
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    @callback
    def close(self):
        self._cancel_auto_off()
        self._listeners.clear()
