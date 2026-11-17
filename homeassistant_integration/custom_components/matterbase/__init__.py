"""Native Matterbase inventory, retaining explicit legacy connector compatibility."""
from pathlib import Path
from homeassistant.components.frontend import async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.helpers.storage import Store
from .api import InventoryView
from .inventory import Inventory

DOMAIN='matterbase'


async def async_setup_entry(hass,entry):
    state=hass.data.setdefault(DOMAIN,{})
    if not state.get('static_registered'):
        await hass.http.async_register_static_paths([
            StaticPathConfig('/matterbase-integration/panel.js',str(Path(__file__).parent/'web/panel.js'),False),
            StaticPathConfig('/matterbase-native',str(Path(__file__).parent/'web/native'),False),
        ])
        hass.http.register_view(InventoryView)
        state['static_registered']=True
    native=entry.data.get('mode')=='native'
    if native:
        inventory=Inventory(Store(hass,1,'matterbase.inventory',private=True,atomic_writes=True,serialize_in_event_loop=False))
        await inventory.load()
        state['inventory']=inventory
        config={'native':True,'pairing_help':entry.options.get('pairing_help',entry.data.get('pairing_help',False))}
    else:
        config={'url':entry.data['url']}
    await async_register_panel(
        hass,frontend_url_path=DOMAIN,webcomponent_name='matterbase-panel',
        sidebar_title='Matterbase',sidebar_icon='mdi:qrcode-scan',
        module_url='/matterbase-integration/panel.js?v=2.0.1',
        config=config,require_admin=True,
    )
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass,entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass,entry):
    async_remove_panel(hass,DOMAIN)
    hass.data.get(DOMAIN,{}).pop('inventory',None)
    return True


async def async_migrate_entry(hass,entry):
    if entry.version==1:
        hass.config_entries.async_update_entry(entry,data={**entry.data,'mode':'external'},version=2)
    return entry.version==2
