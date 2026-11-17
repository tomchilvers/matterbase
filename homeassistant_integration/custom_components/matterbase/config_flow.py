"""Create a native inventory; no external server or Docker setup is needed."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback


class MatterbaseConfigFlow(config_entries.ConfigFlow,domain='matterbase'):
    VERSION=2

    async def async_step_user(self,user_input=None):
        if self._async_current_entries():return self.async_abort(reason='single_instance_allowed')
        if user_input is not None:
            await self.async_set_unique_id('matterbase')
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title='Matterbase',data={'mode':'native','pairing_help':user_input.get('pairing_help',False)})
        return self.async_show_form(step_id='user',data_schema=vol.Schema({vol.Optional('pairing_help',default=False):bool}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MatterbaseOptionsFlow()


class MatterbaseOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self,user_input=None):
        if user_input is not None:return self.async_create_entry(title='',data=user_input)
        default=self.config_entry.options.get('pairing_help',self.config_entry.data.get('pairing_help',False))
        return self.async_show_form(step_id='init',data_schema=vol.Schema({vol.Optional('pairing_help',default=default):bool}))
