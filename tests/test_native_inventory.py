"""Contract checks for native inventory persistence and conflict handling."""
import asyncio
from copy import deepcopy
import importlib
from pathlib import Path
import sys
import types
import pytest

package=types.ModuleType('native_inventory_test')
package.__path__=[str(Path(__file__).resolve().parents[1]/'homeassistant_integration/custom_components/matterbase')]
sys.modules[package.__name__]=package
Inventory=importlib.import_module(package.__name__+'.inventory').Inventory

class Store:
    saved=None
    fail=False
    async def async_load(self):return deepcopy(self.saved)
    async def async_save(self,value):
        if self.fail:raise OSError('Disk full')
        self.saved=deepcopy(value)

def test_native_atomic_conflicts_backup_and_storage_failure():
    async def run():
        store=Store();inventory=Inventory(store)
        device={'qr_payload':'MT:Y.K9042C00KA0648G00','name':'Desk','notes':'Keep','color':'#abcdef','icon':'bulb'}
        assert (await inventory.request('POST','api/devices',{'devices':[device]}))['status']==201
        original=deepcopy(inventory.data)
        assert (await inventory.request('POST','api/devices',{'devices':[device]}))['status']==409
        assert inventory.data==original
        store.fail=True
        with pytest.raises(OSError):await inventory.request('DELETE','api/devices/1')
        assert inventory.data==original
        store.fail=False
        backup=(await inventory.request('GET','api/export'))['body']
        target=Inventory(Store())
        assert (await target.request('POST','api/import',{'devices':[{'device':backup['devices'][0],'action':'add'}]}))['status']==200
        assert target.data['devices'][0]==original['devices'][0]
        restored=Inventory(store);await restored.load();assert restored.data==original
        item={**device,'overwrite_id':1,'expected_revision':1,'name':'Changed'}
        assert (await inventory.request('POST','api/devices',{'devices':[item]}))['status']==200
        assert (await inventory.request('POST','api/devices',{'devices':[item]}))['status']==409
        assert inventory.data['devices'][0]['qr_payload']==device['qr_payload']
    asyncio.run(run())

def test_native_generated_parsers_and_vendor_integrity():
    import hashlib,json
    root=Path(__file__).resolve().parents[1]
    native=root/'homeassistant_integration/custom_components/matterbase'
    for name in ['matter.py','text_recognition.py']:
        assert (root/name).read_bytes()==(native/name).read_bytes()
    vendor=native/'web/native/vendor'
    hashes=json.loads((vendor/'ASSET_HASHES.json').read_text())
    for path,digest in hashes.items():assert hashlib.sha256((vendor/path).read_bytes()).hexdigest()==digest
