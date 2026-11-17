"""Exercise native storage and authorization in a real Home Assistant runtime."""
import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant import loader
from homeassistant.bootstrap import async_from_config_dict
from homeassistant.components.frontend import DATA_PANELS

async def main():
    vendor=Path(__file__).resolve().parents[1]/"custom_components/matterbase/web/native/vendor"
    for path,digest in json.loads((vendor/"ASSET_HASHES.json").read_text()).items():
        assert hashlib.sha256((vendor/path).read_bytes()).hexdigest()==digest
    with tempfile.TemporaryDirectory(prefix='matterbase-ha-') as folder:
        shutil.copytree(Path(__file__).resolve().parents[1]/'custom_components',Path(folder)/'custom_components')
        hass=HomeAssistant(folder)
        loader.async_setup(hass)
        try:
            assert await async_from_config_dict({'http':{'server_host':'127.0.0.1','server_port':18123},'frontend':{}},hass)
            result=await hass.config_entries.flow.async_init('matterbase',context={'source':'user'},data={'pairing_help':False})
            assert result['type']=='create_entry',result
            await asyncio.wait_for(hass.async_block_till_done(),60)
            panel=hass.data[DATA_PANELS]['matterbase']
            assert panel.require_admin and panel.config['native']
            await hass.async_start()
            admin=await hass.auth.async_create_user('Test admin',group_ids=['system-admin'])
            regular=await hass.auth.async_create_user('Test user',group_ids=['system-users'])
            async def token(user):
                return hass.auth.async_create_access_token(await hass.auth.async_create_refresh_token(user,client_id="http://localhost/"))
            admin_token=await token(admin); regular_token=await token(regular)
            async with ClientSession() as session:
                url='http://127.0.0.1:18123/api/matterbase/inventory'
                payload={'method':'GET','path':'api/devices'}
                async with session.post(url,json=payload) as response:assert response.status==401,response.status
                async with session.post(url,json=payload,headers={'Authorization':'Bearer '+regular_token}) as response:assert response.status==403,response.status
                async def api(method,path,body=None):
                    async with session.post(url,json={'method':method,'path':path,'body':body or {}},headers={'Authorization':'Bearer '+admin_token}) as response:
                        assert response.status==200,(response.status,await response.text())
                        return await response.json()
                assert (await api('GET','api/devices'))['body']==[]
                device={'manual_code':'34970112332','brand':'Test','product':'Lamp','name':'Desk','notes':'Keep','icon':'bulb','color':'#abcdef'}
                added=await api('POST','api/devices',{'devices':[device]})
                assert added['status']==201,added
                duplicate=await api('POST','api/devices',{'devices':[device]})
                assert duplicate['status']==409,duplicate
                rows=(await api('GET','api/devices'))['body'];assert len(rows)==1
                backup=(await api('GET','api/export'))['body'];assert backup['version']==1
                assert (await api('POST','api/import/preview',{'backup':backup}))['status']==200
                assert Path(folder,'.storage','matterbase.inventory').exists()
                await hass.config_entries.async_reload(result['result'].entry_id)
                assert (await api('GET','api/devices'))['body']==rows
                async with session.get('http://127.0.0.1:18123/matterbase-native/index.html') as response:
                    assert response.status==200
                    assert 'Desk' not in await response.text()
                await hass.config_entries.async_remove(result['result'].entry_id)
                assert 'matterbase' not in hass.data[DATA_PANELS]
                restored=await hass.config_entries.flow.async_init('matterbase',context={'source':'user'},data={'pairing_help':False})
                await asyncio.wait_for(hass.async_block_till_done(),60)
                assert restored['type']=='create_entry'
                assert (await api('GET','api/devices'))['body']==rows
                entry=restored['result']
                hass.config_entries.async_update_entry(entry,data={'url':'http://legacy.example:8000'},version=1)
                await hass.config_entries.async_reload(entry.entry_id)
                assert entry.version==2 and entry.data['mode']=='external'
                assert hass.data[DATA_PANELS]['matterbase'].config['url']=='http://legacy.example:8000'
            print('PASS: native config flow, admin authorization, CRUD, duplicate conflicts, portable export, persistent storage, reload and reinstallation')
        finally:
            await hass.async_stop()

asyncio.run(main())
