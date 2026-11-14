"""Coordinate vehicle feedback and serialize remote commands for one vehicle."""

import asyncio
import logging
import time
from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta

import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .bluelink_api import BluelinkAPI, BluelinkAuthError, BluelinkError
from .const import BLUELINK_SWITCH_TOGGLE_TIMEOUT, DOMAIN
from .vehicle_status import VehicleStatus

_LOGGER = logging.getLogger(__name__)
STATUS_INTERVAL = timedelta(minutes=5)
STALE_AFTER = timedelta(minutes=15)
COMMAND_POLL_INTERVAL = 5
COMMAND_TIMEOUT = 120
COMMAND_STATES = [
    "idle",
    "sending",
    "accepted",
    "pending",
    "succeeded",
    "failed",
    "timed_out",
    "unconfirmed",
    "authentication_required",
]
BUSY_STATES = {"sending", "accepted", "pending"}


class SharedData:
    """Share confirmed Hyundai state without assuming command acceptance is success."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: BluelinkAPI):
        self.hass = hass
        self.entry = entry
        self.api = api
        self.storage = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.temperature = 72
        self._lock = asyncio.Lock()
        self._listeners: set[Callable] = set()
        self._monitor_task = None
        self._last_toggle: float | None = None
        self._cooldown_cancel = None
        self._unsubscribe_coordinator = None
        self._last_force_refresh: float | None = None
        self._feedback_cancels = []
        self._closed = False
        self._session_closed = False
        self.auth_failed = False
        self.command_status = "idle"
        self.command_action = None
        self.command_started_at = None
        self.command_finished_at = None
        self.command_error = None
        self.cooldown_until = None
        self.last_received_at = None
        self.coordinator = DataUpdateCoordinator[VehicleStatus](
            hass,
            _LOGGER,
            config_entry=entry,
            name="Bluelink vehicle status",
            update_interval=STATUS_INTERVAL,
            update_method=self._async_fetch_status,
        )

    @property
    def status(self):
        return self.coordinator.data

    @property
    def is_on(self):
        return self.status.climate_on if self.status is not None else None

    @property
    def is_stale(self):
        return (
            self.status is None
            or self.status.updated_at is None
            or not self.coordinator.last_update_success
            or dt_util.utcnow() - self.status.updated_at > STALE_AFTER
            or self.status.updated_at > dt_util.utcnow() + timedelta(minutes=5)
        )

    @property
    def busy(self):
        return self.command_status in BUSY_STATES

    async def load_data(self):
        data = await self.storage.async_load()
        migrated = data is None
        if data is None:
            data = await Store(self.hass, 1, "bluelink_climate.json").async_load()
        if (
            data
            and isinstance(value := data.get("temperature"), (int, float))
            and 62 <= value <= 82
        ):
            self.temperature = value
            if migrated:
                await self.storage.async_save({"temperature": value})

    async def async_initialize(self):
        """Missing telemetry must not prevent the user from issuing a command."""
        await self.coordinator.async_refresh()
        if not self.auth_failed:
            self._unsubscribe_coordinator = self.coordinator.async_add_listener(
                self._notify
            )

    async def store_data(self, temperature):
        await self.storage.async_save({"temperature": temperature})
        self.temperature = temperature
        self._notify()

    @callback
    def subscribe(self, listener):
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    @callback
    def _notify(self):
        if not self._closed:
            for listener in tuple(self._listeners):
                listener()

    @callback
    def save_auth(self):
        auth = self.api.auth
        if auth != self.entry.data.get("auth"):
            self.hass.config_entries.async_update_entry(
                self.entry, data={**self.entry.data, "auth": auth}
            )

    async def _async_api_job(self, method, *args):
        """Finish in-flight executor I/O before releasing the shared session lock."""
        job = self.hass.async_add_executor_job(method, *args)
        try:
            return await asyncio.shield(job)
        except asyncio.CancelledError:
            with suppress(Exception):
                await job
            raise
        finally:
            self.save_auth()

    @callback
    def _auth_failed(self, *, start_reauth=True):
        if not self.auth_failed:
            self.auth_failed = True
            if start_reauth:
                self.entry.async_start_reauth(self.hass)
        self.command_status = "authentication_required"
        self.command_error = "Sign in again in Settings > Devices & services"
        self._notify()

    async def _async_fetch_status(self):
        async with self._lock:
            if self._closed:
                return self.status
            try:
                status = await self._async_api_job(self.api.get_vehicle_status)
            except BluelinkAuthError as err:
                self._auth_failed(start_reauth=False)
                raise ConfigEntryAuthFailed("Sign in to Bluelink again") from err
            except (requests.RequestException, BluelinkError) as err:
                raise UpdateFailed("Unable to read Hyundai vehicle status") from err
            self.last_received_at = dt_util.utcnow()
            # Never let an out-of-order cache response replace newer car data.
            if (
                self.status is not None
                and self.status.updated_at is not None
                and (
                    status.updated_at is None
                    or status.updated_at < self.status.updated_at
                )
            ):
                return self.status
            return status

    async def async_refresh_status(self, force=False):
        """A normal refresh reads the cache. Waking the car requires an explicit press."""
        if self._closed:
            return
        if self.auth_failed:
            raise HomeAssistantError(
                "Sign in to Bluelink again in Settings > Devices & services"
            )
        if force:
            async with self._lock:
                if (
                    self._last_force_refresh is not None
                    and time.monotonic() - self._last_force_refresh < 60
                ):
                    raise ServiceValidationError(
                        "Wait 60 seconds before requesting fresh vehicle status again"
                    )
                self._last_force_refresh = time.monotonic()
                try:
                    status = await self._async_api_job(
                        self.api.get_vehicle_status, True
                    )
                except BluelinkAuthError as err:
                    self._auth_failed()
                    raise HomeAssistantError("Bluelink needs reauthentication") from err
                except (requests.RequestException, BluelinkError) as err:
                    raise HomeAssistantError(
                        "Hyundai could not refresh vehicle status"
                    ) from err
                self.last_received_at = dt_util.utcnow()
                if (
                    self.status is None
                    or self.status.updated_at is None
                    or (
                        status.updated_at is not None
                        and status.updated_at >= self.status.updated_at
                    )
                ):
                    self.coordinator.async_set_updated_data(status)
        else:
            await self.coordinator.async_request_refresh()
            if not self.coordinator.last_update_success:
                raise HomeAssistantError(
                    "Hyundai vehicle status is unavailable; the last snapshot has been retained"
                )
        self._notify()

    async def async_set_running(self, running: bool):
        async with self._lock:
            if self._closed:
                raise HomeAssistantError("Bluelink is unloading")
            if self.auth_failed:
                raise HomeAssistantError(
                    "Bluelink needs reauthentication in Settings > Devices & services"
                )
            if self.busy:
                if self.command_action == ("start" if running else "stop"):
                    return
                raise ServiceValidationError(
                    "Wait for the current Hyundai command to finish"
                )
            if (
                self._last_toggle is not None
                and time.monotonic() - self._last_toggle
                < BLUELINK_SWITCH_TOGGLE_TIMEOUT
            ):
                raise ServiceValidationError(
                    "Wait 60 seconds between Bluelink climate commands; see Next command available"
                )
            self.command_status = "sending"
            self.command_action = "start" if running else "stop"
            self.command_started_at = dt_util.utcnow()
            self.command_finished_at = None
            self.command_error = None
            # The request may reach Hyundai even when the response times out.
            self._last_toggle = time.monotonic()
            self.cooldown_until = self.command_started_at + timedelta(
                seconds=BLUELINK_SWITCH_TOGGLE_TIMEOUT
            )
            if self._cooldown_cancel is not None:
                self._cooldown_cancel()
            self._cooldown_cancel = async_call_later(
                self.hass, BLUELINK_SWITCH_TOGGLE_TIMEOUT, self._end_cooldown
            )
            self._notify()
            try:
                if running:
                    transaction = await self._async_api_job(
                        self.api.start_climate, self.temperature
                    )
                else:
                    transaction = await self._async_api_job(self.api.stop_climate)
            except BluelinkAuthError as err:
                self._auth_failed()
                raise HomeAssistantError(
                    "Bluelink needs reauthentication in Settings > Devices & services"
                ) from err
            except (requests.RequestException, BluelinkError) as err:
                self._finish_command(
                    "unconfirmed",
                    "Hyundai did not confirm acceptance. Check vehicle status before retrying.",
                )
                self._schedule_feedback_refreshes()
                raise HomeAssistantError(self.command_error) from err
            self.command_status = "accepted" if transaction else "unconfirmed"
            if not transaction:
                self.command_error = "Hyundai accepted the request without a tracking ID; completion cannot be verified"
                self.command_finished_at = dt_util.utcnow()
            self._notify()
            self._monitor_task = self.hass.async_create_background_task(
                self._monitor_command(transaction), "Bluelink command feedback"
            )
            self._schedule_feedback_refreshes()

    @callback
    def _schedule_feedback_refreshes(self):
        for cancel in self._feedback_cancels:
            cancel()
        self._feedback_cancels = [
            async_call_later(self.hass, delay, self._async_refresh_feedback)
            for delay in (15, 30, 60)
        ]

    async def _async_refresh_feedback(self, _now):
        """Allow the Hyundai cache to catch up without waking the vehicle."""
        if self._closed or self.auth_failed:
            return
        if (
            not self.is_stale
            and self.status.updated_at >= self.command_started_at
            and self.is_on == (self.command_action == "start")
        ):
            return
        await self.coordinator.async_refresh()

    @callback
    def _finish_command(self, status, error=None):
        self.command_status = status
        self.command_error = error
        self.command_finished_at = dt_util.utcnow()
        self._notify()

    async def _monitor_command(self, transaction):
        try:
            if transaction:
                self.command_status = "pending"
                self._notify()
                deadline = time.monotonic() + COMMAND_TIMEOUT
                while time.monotonic() < deadline:
                    await asyncio.sleep(COMMAND_POLL_INTERVAL)
                    async with self._lock:
                        try:
                            result = await self._async_api_job(
                                self.api.check_action_status, transaction
                            )
                        except BluelinkAuthError:
                            self._auth_failed()
                            return
                        except (requests.RequestException, BluelinkError):
                            # Keep trying for the bounded monitoring period.
                            continue
                    if result in {"succeeded", "failed"}:
                        self._finish_command(
                            result,
                            "Hyundai reported that the command failed"
                            if result == "failed"
                            else None,
                        )
                        break
                else:
                    self._finish_command(
                        "timed_out",
                        "Hyundai did not confirm completion within two minutes; the result is unknown",
                    )
            # Read cache only. Command success must never imply a fresh vehicle snapshot.
            await self.coordinator.async_refresh()
        except asyncio.CancelledError:
            raise
        finally:
            self._notify()

    @callback
    def _end_cooldown(self, _now):
        self._cooldown_cancel = None
        self.cooldown_until = None
        self._notify()

    @callback
    def close(self):
        self._closed = True
        for cancel in self._feedback_cancels:
            cancel()
        self._feedback_cancels.clear()
        if self._cooldown_cancel is not None:
            self._cooldown_cancel()
            self._cooldown_cancel = None
        if self._unsubscribe_coordinator is not None:
            self._unsubscribe_coordinator()
            self._unsubscribe_coordinator = None
        if self._monitor_task is not None:
            self._monitor_task.cancel()
        self._listeners.clear()

    async def async_close(self):
        self.close()
        await self.coordinator.async_shutdown()
        if self._monitor_task is not None:
            await asyncio.gather(self._monitor_task, return_exceptions=True)
        async with self._lock:
            if not self._session_closed:
                await self.hass.async_add_executor_job(self.api.close)
                self._session_closed = True
