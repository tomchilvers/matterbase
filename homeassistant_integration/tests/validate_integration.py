"""Exercise config flow, panel registration and unload in real Home Assistant."""
import asyncio
from pathlib import Path
import shutil
import tempfile
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant import loader
from homeassistant.bootstrap import async_from_config_dict
from homeassistant.components.frontend import DATA_PANELS


async def main():
    requests=[]
    mode={"status":503,"ancestors":"'none'"}
    async def health(request):
        requests.append(request.path)
        assert request.path=='/api/health'
        return web.json_response({'status':'ok'},status=mode['status'],headers={'Content-Security-Policy':"frame-ancestors "+mode['ancestors']})
    backend=web.Application();backend.router.add_get('/api/health',health)
    runner=web.AppRunner(backend);await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    port=site._server.sockets[0].getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='matterbase-ha-') as folder:
        source=Path(__file__).resolve().parents[1]/'custom_components'
        shutil.copytree(source,Path(folder)/'custom_components')
        hass=HomeAssistant(folder)
        loader.async_setup(hass)
        try:
            assert await async_from_config_dict({'http':{'server_host':'127.0.0.1','server_port':18123},'frontend':{}},hass)
            flow=await hass.config_entries.flow.async_init('matterbase',context={'source':'user'},data={'url':'file:///etc/passwd'})
            assert flow['type']=='form' and flow['errors']['url']=='invalid_url',flow
            server={'url':f'http://127.0.0.1:{port}'}
            retry=await hass.config_entries.flow.async_configure(flow['flow_id'],server)
            assert retry['type']=='form' and retry['errors']['base']=='cannot_connect',retry
            mode['status']=200
            retry=await hass.config_entries.flow.async_configure(flow['flow_id'],server)
            assert retry['type']=='form' and retry['errors']['base']=='embedding_disabled',retry
            mode['ancestors']="'self' https://ha.example.com"
            result=await hass.config_entries.flow.async_configure(flow['flow_id'],server)
            assert result['type']=='create_entry',result
            await asyncio.wait_for(hass.async_block_till_done(),60)
            panel=hass.data[DATA_PANELS]['matterbase']
            assert panel.require_admin and panel.config['url']==f'http://127.0.0.1:{port}'
            assert panel.config['_panel_custom']['module_url']=='/matterbase-integration/panel.js?v=1.0.0'
            duplicate=await hass.config_entries.flow.async_init('matterbase',context={'source':'user'})
            assert duplicate['type']=='abort' and duplicate['reason']=='single_instance_allowed'
            await hass.config_entries.async_remove(result['result'].entry_id)
            assert 'matterbase' not in hass.data[DATA_PANELS]
            assert requests==['/api/health']*3,requests
            print('PASS: real Home Assistant config flow, URL validation, health request, admin sidebar, duplicate guard and unload')
        finally:
            await hass.async_stop()
            await runner.cleanup()


asyncio.run(main())
