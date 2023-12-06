"""Support for Tesla cars."""
import asyncio
from datetime import timedelta
from functools import partial
from http import HTTPStatus
import logging

import async_timeout
import httpx

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_CLOSE,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .config_flow import CannotConnect, InvalidAuth, validate_input
from .const import (
    CONF_INCLUDE_VEHICLES,
    CONF_POLLING_POLICY,
    CONF_WAKE_ON_START,
    DATA_LISTENER,
    DEFAULT_POLLING_POLICY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WAKE_ON_START,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    PLATFORMS,
    CONF_BASE_URL,
    CONF_WRAPPER_API_KEY,
    BASE_URL,
    WRAPPER_API_KEY,
)
from .services import async_setup_services, async_unload_services
from .tesla_custom_lib.controller import Controller as TeslaAPI
from .tesla_custom_lib.exceptions import IncompleteCredentials, TeslaException
from .util import SSL_CONTEXT

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@callback
def _async_configured_base_url(hass):
    """Return a set of configured Tesla emails."""
    return {
        entry.data[CONF_USERNAME]
        for entry in hass.config_entries.async_entries(DOMAIN)
        if CONF_USERNAME in entry.data
    }


async def async_setup(hass, base_config):
    """Set up of Tesla component."""

    def _update_entry(base_url, data=None, options=None):
        data = data or {}
        options = options or {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_WAKE_ON_START: DEFAULT_WAKE_ON_START,
            CONF_POLLING_POLICY: DEFAULT_POLLING_POLICY,
        }
        for entry in hass.config_entries.async_entries(DOMAIN):
            if base_url != entry.title:
                continue
            hass.config_entries.async_update_entry(entry, data=data, options=options)

    config = base_config.get(DOMAIN)

    if not config:
        return True

    base_url = BASE_URL  #hier eigl. input values os config
    wrapper_api_key = WRAPPER_API_KEY
    scan_interval = DEFAULT_SCAN_INTERVAL

    if "Testing_test" in _async_configured_base_url(hass):
        try:
            info = await validate_input(hass, config)
        except (CannotConnect, InvalidAuth):
            return False
        _update_entry(
            base_url,
            data={
                CONF_USERNAME: "Testing_test",
                "base_url": base_url,
                "wrapper_api_key": wrapper_api_key
            },
            options={CONF_SCAN_INTERVAL: scan_interval},
        )
    else:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
               data={
                CONF_USERNAME: "Testing_test",
                "base_url": base_url,
                "wrapper_api_key": wrapper_api_key
            },
            )
        )
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["Testing_test"] = {CONF_SCAN_INTERVAL: scan_interval}

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Tesla as config entry."""
    # pylint: disable=too-many-locals,too-many-statements
    hass.data.setdefault(DOMAIN, {})
    config = config_entry.data
    # Because users can have multiple accounts, we always
    # create a new session so they have separate cookies
    async_client = httpx.AsyncClient(
        timeout=60, verify=SSL_CONTEXT  # Removed user context header
    )
    username = config_entry.title

    if not hass.data[DOMAIN]:
        async_setup_services(hass)

    if (
        username in hass.data[DOMAIN]
        and CONF_SCAN_INTERVAL in hass.data[DOMAIN][username]
    ):
        scan_interval = hass.data[DOMAIN][username][CONF_SCAN_INTERVAL]
        hass.config_entries.async_update_entry(
            config_entry, options={CONF_SCAN_INTERVAL: scan_interval}
        )
        hass.data[DOMAIN].pop(username)

    try:
        controller = TeslaAPI(
            async_client,
            wrapper_api_key= WRAPPER_API_KEY,
            polling_policy=config_entry.options.get(
                CONF_POLLING_POLICY, DEFAULT_POLLING_POLICY
            ),
        )
        result = await controller.connect()

    except IncompleteCredentials as ex:
        await async_client.aclose()
        raise ConfigEntryAuthFailed from ex

    except (httpx.ConnectTimeout, httpx.ConnectError) as ex:
        await async_client.aclose()
        raise ConfigEntryNotReady from ex

    except TeslaException as ex:
        await async_client.aclose()

        if ex.code == HTTPStatus.UNAUTHORIZED:
            raise ConfigEntryAuthFailed from ex

        if ex.message in [
            "TOO_MANY_REQUESTS",
            "UPSTREAM_TIMEOUT",
        ]:
            raise ConfigEntryNotReady(
                f"Temporarily unable to communicate with Tesla API: {ex.message}"
            ) from ex

        _LOGGER.error("Unable to communicate with Tesla API: %s", ex.message)

        return False

    async def _async_close_client(*_):
        await async_client.aclose()

    @callback
    def _async_create_close_task():
        # Background tasks are tracked in HA to prevent them from
        # being garbage collected in the middle of the task since
        # asyncio only holds a weak reference to them.
        #
        # https://docs.python.org/3/library/asyncio-task.html#creating-tasks

        if hasattr(hass, "async_create_background_task"):
            hass.async_create_background_task(
                _async_close_client(), "tesla_close_client"
            )
        else:
            asyncio.create_task(_async_close_client())

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _async_close_client)
    )
    config_entry.async_on_unload(_async_create_close_task)

    try:
        if config_entry.data.get("initial_setup"):
            wake_if_asleep = True
        else:
            wake_if_asleep = config_entry.options.get(
                CONF_WAKE_ON_START, DEFAULT_WAKE_ON_START
            )

        cars = await controller.generate_car_objects(wake_if_asleep=wake_if_asleep)

        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data, "initial_setup": False}
        )

    except TeslaException as ex:
        await async_client.aclose()

        if ex.message in [
            "TOO_MANY_REQUESTS",
            "SERVICE_MAINTENANCE",
            "UPSTREAM_TIMEOUT",
        ]:
            raise ConfigEntryNotReady(
                f"Temporarily unable to communicate with Tesla API: {ex.message}"
            ) from ex

        _LOGGER.error("Unable to communicate with Tesla API: %s", ex.message)

        return False

    reload_lock = asyncio.Lock()
    _partial_coordinator = partial(
        TeslaDataUpdateCoordinator,
        hass,
        config_entry=config_entry,
        controller=controller,
        reload_lock=reload_lock,
        vins=set(),
        update_vehicles=False,
    )
    car_coordinators = {vin: _partial_coordinator(vins={vin}) for vin in cars}
    coordinators = {**car_coordinators}

    if car_coordinators:
        update_vehicles_coordinator = _partial_coordinator(update_vehicles=True)
        coordinators["update_vehicles"] = update_vehicles_coordinator

        # If we have cars, we want to update the vehicles coordinator
        # to keep the vehicles up to date.
        @callback
        def _async_update_vehicles():
            """Update vehicles coordinator.

            This listener is called when the update_vehicles_coordinator
            is updated. Since each car coordinator is also polling we don't
            need to do anything here, but we need to have this listener
            to ensure the update_vehicles_coordinator is updated regularly.
            """

        update_vehicles_coordinator.async_add_listener(_async_update_vehicles)

    hass.data[DOMAIN][config_entry.entry_id] = {
        "controller": controller,
        "coordinators": coordinators,
        "cars": cars,
    }
    _LOGGER.debug("Connected to the Tesla API")

    # We do not do a first refresh as we already know the API is working
    # from above. Each platform will schedule a refresh via update_before_add
    # for the sites/vehicles they are interested in.

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, config_entry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    controller: TeslaAPI = entry_data["controller"]
    await controller.disconnect()

    for listener in entry_data[DATA_LISTENER]:
        listener()
    username = config_entry.title

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        _LOGGER.debug("Unloaded entry for %s", username)

        if not hass.data[DOMAIN]:
            async_unload_services(hass)

        return True

    return False


async def update_listener(hass, config_entry):
    """Update when config_entry options update."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    controller: TeslaAPI = entry_data["controller"]
    old_update_interval = controller.update_interval
    controller.update_interval = config_entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    )
    if old_update_interval != controller.update_interval:
        _LOGGER.debug(
            "Changing scan_interval from %s to %s",
            old_update_interval,
            controller.update_interval,
        )


class TeslaDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Tesla data."""

    def __init__(
        self,
        hass,
        *,
        config_entry,
        controller: TeslaAPI,
        reload_lock: asyncio.Lock,
        vins: set[str],
        update_vehicles: bool,
    ):
        """Initialize global Tesla data updater."""
        self.controller = controller
        self.config_entry = config_entry
        self.reload_lock = reload_lock
        self.vins = vins
        self.update_vehicles = update_vehicles
        self._debounce_task = None
        self._last_update_time = None

        update_interval = timedelta(seconds=MIN_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(30):
                _LOGGER.debug("Running controller.update()")
                return await self.controller.update(
                    vins=self.vins,
                    update_vehicles=self.update_vehicles,
                )
        except IncompleteCredentials:
            if self.reload_lock.locked():
                # Any of the coordinators can trigger a reload, but we only
                # want to do it once. If the lock is already locked, we know
                # another coordinator is already reloading.
                _LOGGER.debug("Config entry is already being reloaded")
                return
            async with self.reload_lock:
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        except TeslaException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        # Sollte deactive sein

    def async_update_listeners_debounced(self, delay_since_last=0.1, max_delay=1.0):
        """Debounced version of async_update_listeners.

        This function cancels the previous task (if any) and creates a new one.

        Parameters
        ----------
        delay_since_last : float
            Minimum delay in seconds since the last received message before calling async_update_listeners.
        max_delay : float
            Maximum delay in seconds before calling async_update_listeners,
            regardless of when the last message was received.

        """
        # If there's an existing debounce task, cancel it
        if self._debounce_task:
            self._debounce_task()
            _LOGGER.debug("Previous debounce task cancelled")

        # Schedule the call to _debounced, pass max_delay using partial
        self._debounce_task = async_call_later(
            self.hass, delay_since_last, partial(self._debounced, max_delay)
        )
        _LOGGER.debug("New debounce task scheduled")

    async def _debounced(self, max_delay, *args):
        """Debounce method that waits a certain delay since the last update.

        This method ensures that async_update_listeners is called at least every max_delay seconds.

        Parameters
        ----------
        max_delay : float
            Maximum delay in seconds before calling async_update_listeners.

        """
        # Get the current time
        now = self.hass.loop.time()

        # If it's been at least max_delay since the last update (or there was no previous update),
        # call async_update_listeners and update the last update time
        if not self._last_update_time or now - self._last_update_time >= max_delay:
            self._last_update_time = now
            self.async_update_listeners()
            _LOGGER.debug("Listeners updated")
        else:
            # If it hasn't been max_delay since the last update,
            # schedule the call to _debounced again after the remaining time
            self._debounce_task = async_call_later(
                self.hass,
                max_delay - (now - self._last_update_time),
                partial(self._debounced, max_delay),
            )
            _LOGGER.debug("Max delay not reached, scheduling another debounce task")
