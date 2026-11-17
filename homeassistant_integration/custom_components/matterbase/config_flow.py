"""Configure one existing Matterbase server and its sidebar panel."""
from aiohttp import ClientError
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .connection import EmbeddingDisabled, server_url, validate_server


class MatterbaseConfigFlow(config_entries.ConfigFlow, domain="matterbase"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            try:
                url = server_url(user_input["url"])
            except ValueError:
                errors["url"] = "invalid_url"
            else:
                try:
                    await validate_server(async_get_clientsession(self.hass), url)
                except EmbeddingDisabled:
                    errors["base"] = "embedding_disabled"
                except (ClientError, TimeoutError, ValueError, AttributeError):
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id("matterbase")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Matterbase", data={"url": url})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required("url"): str}), errors=errors)
