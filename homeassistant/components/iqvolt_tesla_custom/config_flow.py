"""Tesla Config Flow."""
from http import HTTPStatus
import logging

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_SCAN_INTERVAL,

)

from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import SERVER_SOFTWARE, USER_AGENT
import httpx
from .tesla_custom_lib.controller import Controller as TeslaAPI
from .tesla_custom_lib.exceptions import IncompleteCredentials, TeslaException
import voluptuous as vol

from .const import (
    ATTR_POLLING_POLICY_ALWAYS,
    ATTR_POLLING_POLICY_CONNECTED,
    ATTR_POLLING_POLICY_NORMAL,
    CONF_POLLING_POLICY,
    CONF_WAKE_ON_START,
    DEFAULT_POLLING_POLICY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WAKE_ON_START,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    CONF_BASE_URL,
    CONF_WRAPPER_API_KEY,
    BASE_URL,
    WRAPPER_API_KEY,
)
from .util import SSL_CONTEXT

_LOGGER = logging.getLogger(__name__)


class TeslaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tesla."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the tesla flow."""
        self.wrapper_api_key = None
        self.base_url = None

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step(import_config)

    async def async_step(self, user_input=None):
        """Handle the start of the config flow."""
        errors = {}

        if user_input is not None:
            existing_entry = self._async_entry_for_base_url(user_input[CONF_BASE_URL])
            if existing_entry:
                return self.async_abort(reason="already_configured")

            try:
                info = await validate_input(self.hass, user_input)
                # Used for only forcing cars awake on initial setup in async_setup_entry
                info.update({"initial_setup": True})
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"

            if not errors:
                if existing_entry:
                    self.hass.config_entries.async_update_entry( # Update Eintrag
                        existing_entry, data=info
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)  # Reload of new data/ establish new connection???
                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(  # Neuer Eintrag
                    title=user_input[CONF_BASE_URL], data=info
                )

        return self.async_show_form(
            step_id="Setup Wrapper API",
            data_schema=self._async_schema(),
            errors=errors,
            description_placeholders={},
        )


    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    @callback
    def _async_schema(self):
        """Fetch schema with defaults."""
        return vol.Schema(
            {
                vol.Required(CONF_BASE_URL): str,
            },
            {
                vol.Required(CONF_WRAPPER_API_KEY): str,
            }
        )

    @callback
    def _async_entry_for_base_url(self, base_url):
        """Find an existing entry for a Base URL."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_BASE_URL) == base_url:
                return entry
        return None


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Tesla."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None): # Sollte passen
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="Optional", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
                vol.Optional(
                    CONF_WAKE_ON_START,
                    default=self.config_entry.options.get(
                        CONF_WAKE_ON_START, DEFAULT_WAKE_ON_START
                    ),
                ): bool,
                vol.Required(
                    CONF_POLLING_POLICY,
                    default=self.config_entry.options.get(
                        CONF_POLLING_POLICY, DEFAULT_POLLING_POLICY
                    ),
                ): vol.In(
                    [
                        ATTR_POLLING_POLICY_NORMAL,
                        ATTR_POLLING_POLICY_CONNECTED,
                        ATTR_POLLING_POLICY_ALWAYS,
                    ]
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


async def validate_input(hass: core.HomeAssistant, data) -> dict: # Sollte Passen
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    config = {}
    async_client = httpx.AsyncClient(
        headers={USER_AGENT: SERVER_SOFTWARE}, timeout=60, verify=SSL_CONTEXT  #TODO: Potential direct injection for SSL_Context
    )

    try:
        controller = TeslaAPI(
            async_client,
            wrapper_api_key=data[CONF_WRAPPER_API_KEY],
            base_url=data[CONF_BASE_URL],
          #  polling_policy=data.get(CONF_POLLING_POLICY, DEFAULT_POLLING_POLICY),
        )
        await controller.connect()

    except IncompleteCredentials as ex:
        _LOGGER.error("Authentication error: %s %s", ex.message, ex)
        raise InvalidAuth() from ex
    except TeslaException as ex:
        if ex.code == HTTPStatus.UNAUTHORIZED or isinstance(ex, IncompleteCredentials):
            _LOGGER.error("Invalid credentials: %s", ex.message)
            raise InvalidAuth() from ex
        _LOGGER.error("Unable to communicate with Tesla API: %s", ex.message)
        raise CannotConnect() from ex
    finally:
        await async_client.aclose()
    _LOGGER.debug("Credentials successfully connected to the Tesla API")
    return config


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
