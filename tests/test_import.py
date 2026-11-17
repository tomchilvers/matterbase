import pytest
from app import create_app
QR='MT:EX7A00O6148-.548G00'
OTHER='14970212332'
@pytest.fixture
def client(tmp_path):
    return create_app(tmp_path).test_client()
def backup(client):
    return client.get('/api/export').json
def preview(client,data):
    return client.post('/api/import/preview',json={'backup':data})
def apply(client,entries):
    return client.post('/api/import',json={'devices':entries})
def seed(client):
    assert client.post('/api/devices',json={'devices':[{'qr_payload':QR,'name':'Lamp','brand':'IKEA','product':'KAJPLATS','notes':'Line one\nLine two','color':'#6a9a8b','icon':'bulb'}]}).status_code==201

def test_export_restore_roundtrip_preserves_all_portable_fields(client,tmp_path):
    seed(client)
    data=backup(client)
    target=create_app(tmp_path/'other').test_client()
    response=preview(target,data)
    assert response.status_code==200
    assert target.get('/api/devices').json==[]
    entries=[{**entry,'action':'add'} for entry in response.json['devices']]
    assert apply(target,entries).json=={'created':1,'updated':0,'skipped':0}
    restored=backup(target)['devices'][0]
    assert restored==data['devices'][0]
    assert target.get(f"/api/devices/{restored['id']}/qr").status_code==200

def test_skip_then_explicit_overwrite_preserves_local_identity(client):
    seed(client);data=backup(client);original=data['devices'][0]
    data['devices'][0]={**original,'name':'Restored lamp','notes':'  original whitespace\n','created_at':'2020-01-01T00:00:00Z'}
    entry=preview(client,data).json['devices'][0]
    assert entry['original']['name']=='Lamp'
    assert apply(client,[{**entry,'action':'skip'}]).json['skipped']==1
    assert backup(client)['devices'][0]==original
    result=apply(client,[{**entry,'action':'overwrite','expected_id':original['id'],'expected_revision':original['revision']}])
    assert result.status_code==200
    restored=backup(client)['devices'][0]
    assert restored['id']==original['id'] and restored['revision']==original['revision']+1
    assert restored['notes']=='  original whitespace\n'
    assert restored['created_at']=='2020-01-01T00:00:00Z'

def test_import_race_rolls_back_all_changes(client):
    seed(client);data=backup(client);original=data['devices'][0]
    entry=preview(client,data).json['devices'][0]
    client.put(f"/api/devices/{original['id']}",json={**original,'name':'Changed elsewhere'})
    before=backup(client)['devices']
    result=apply(client,[{'device':{'manual_code':OTHER},'action':'add'},{**entry,'action':'overwrite','expected_id':original['id'],'expected_revision':original['revision']}])
    assert result.status_code==409
    assert backup(client)['devices']==before

def test_new_duplicate_since_preview_requires_new_preview(client):
    data={'version':1,'devices':[{'manual_code':OTHER}]}
    entry=preview(client,data).json['devices'][0]
    client.post('/api/devices',json=data)
    assert apply(client,[{**entry,'action':'add'}]).status_code==409

@pytest.mark.parametrize('data',[{},[],{'version':2,'devices':[]},{'version':True,'devices':[]},{'version':1,'devices':None},{'version':1,'devices':[None]},{'version':1,'devices':[{'manual_code':'bad'}]},{'version':1,'devices':[{'manual_code':OTHER,'created_at':'invalid'}]},{'version':1,'devices':[{'manual_code':OTHER,'created_at':'2020-01-01'}]},{'version':1,'devices':[{'manual_code':OTHER}]*2}])
def test_invalid_backup_has_no_writes(client,data):
    assert preview(client,data).status_code==400
    assert client.get('/api/devices').json==[]

def test_empty_backup_is_valid_and_exported(client):
    data=backup(client)
    assert preview(client,data).json=={'devices':[]}
    assert apply(client,[]).json=={'created':0,'updated':0,'skipped':0}

def test_import_keeps_records_missing_from_backup(client):
    seed(client)
    assert apply(client,[{'device':{'manual_code':OTHER},'action':'add'}]).status_code==200
    assert len(client.get('/api/devices').json)==2

def test_invalid_later_record_rolls_back(client):
    result=apply(client,[{'device':{'manual_code':OTHER},'action':'add'},{'device':{'qr_payload':QR},'action':'invalid'}])
    assert result.status_code==400
    assert client.get('/api/devices').json==[]
