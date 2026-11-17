import pytest
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from app import create_app

CODE = '00054912336'
QR = 'MT:EX7A00O6148-.548G00'
OTHER = '14970212332'


@pytest.fixture
def client(tmp_path):
    return create_app(tmp_path).test_client()


def seed(client):
    client.post('/api/devices',json={'devices':[{'qr_payload':QR,'name':'Hallway lamp',
        'notes':'Do not lose this note','brand':'IKEA','product':'Original product','color':'#6a9a8b','icon':'bulb'}]})
    return client.get('/api/devices').json[0]


def test_duplicate_requires_explicit_choice_and_returns_original(client):
    original=seed(client)
    response=client.post('/api/devices',json={'devices':[{'manual_code':'0005-491-2336','product':'New product'}]})
    assert response.status_code==409
    assert response.json['conflicts'][0]['id']==original['id']
    assert response.json['conflicts'][0]['name']=='Hallway lamp'
    assert client.get('/api/devices').json==[original]


def test_explicit_overwrite_updates_same_record_and_preserves_metadata(client):
    original=seed(client)
    response=client.post('/api/devices',json={'devices':[{'manual_code':CODE,
        'overwrite_id':original['id'],'expected_revision':original['revision'],'product':'KAJPLATS KIT'}]})
    assert response.status_code==200
    assert response.json=={'saved':1,'created':0,'updated':1}
    record=client.get('/api/devices').json[0]
    assert record['id']==original['id'] and record['created_at']==original['created_at']
    assert record['revision']==original['revision']+1
    assert record['product']=='KAJPLATS KIT'
    for field in ('manual_code','qr_payload','name','notes','brand','color','icon'):
        assert record[field]==original[field]


def test_overwrite_allows_deliberate_clearing(client):
    original=seed(client)
    response=client.post('/api/devices',json={'devices':[{'manual_code':CODE,
        'overwrite_id':original['id'],'expected_revision':original['revision'],
        'name':'','notes':'','color':'','icon':''}]})
    assert response.status_code==200
    record=client.get('/api/devices').json[0]
    assert all(record[field]=='' for field in ('name','notes','color','icon'))
    assert record['qr_payload']==QR


def test_mixed_create_and_overwrite_is_one_transaction(client):
    original=seed(client)
    response=client.post('/api/devices',json={'devices':[{'manual_code':OTHER,'name':'New bulb'},
        {'manual_code':CODE,'overwrite_id':original['id'],'expected_revision':original['revision'],'product':'Updated'}]})
    assert response.status_code==201
    assert response.json=={'saved':2,'created':1,'updated':1}
    records=client.get('/api/devices').json
    assert len(records)==2
    assert next(d for d in records if d['id']==original['id'])['product']=='Updated'


def test_stale_overwrite_rejects_entire_batch_and_returns_fresh_original(client):
    original=seed(client)
    fresh={**original,'name':'Renamed elsewhere'}
    client.put(f"/api/devices/{original['id']}",json=fresh)
    before=client.get('/api/devices').json
    response=client.post('/api/devices',json={'devices':[{'manual_code':OTHER},
        {'manual_code':CODE,'overwrite_id':original['id'],'expected_revision':original['revision'],'product':'Stale scan'}]})
    assert response.status_code==409
    assert response.json['conflicts'][0]['name']=='Renamed elsewhere'
    assert client.get('/api/devices').json==before


@pytest.mark.parametrize('target,revision',[(None,1),(True,1),('1',1),(1,None),(1,True),(1,0)])
def test_overwrite_requires_valid_id_and_revision(client,target,revision):
    before=seed(client)
    response=client.post('/api/devices',json={'devices':[{'manual_code':CODE,
        'overwrite_id':target,'expected_revision':revision}]})
    assert response.status_code==400
    assert client.get('/api/devices').json==[before]


def test_cannot_overwrite_a_different_pairing_code(client):
    original=seed(client)
    response=client.post('/api/devices',json={'devices':[{'manual_code':OTHER,
        'overwrite_id':original['id'],'expected_revision':original['revision']}]})
    assert response.status_code==400
    assert client.get('/api/devices').json==[original]


def test_deleted_original_does_not_save_other_items(client):
    original=seed(client)
    client.delete(f"/api/devices/{original['id']}")
    response=client.post('/api/devices',json={'devices':[{'manual_code':OTHER},
        {'manual_code':CODE,'overwrite_id':original['id'],'expected_revision':original['revision']}]})
    assert response.status_code==409
    assert client.get('/api/devices').json==[]


@pytest.mark.parametrize('legacy',[False,True])
def test_workers_can_initialise_and_migrate_the_same_database(tmp_path,legacy):
    if legacy:
        with sqlite3.connect(tmp_path/'matterbase.sqlite3') as conn:
            conn.execute("""CREATE TABLE devices (id INTEGER PRIMARY KEY,brand TEXT DEFAULT '',
                product TEXT DEFAULT '',name TEXT DEFAULT '',notes TEXT DEFAULT '',manual_code TEXT UNIQUE,
                qr_payload TEXT DEFAULT '',vendor_id INTEGER,product_id INTEGER,
                created_at TEXT DEFAULT '',updated_at TEXT DEFAULT '')""")
            conn.execute("INSERT INTO devices (manual_code,notes) VALUES (?,?)",(CODE,'Existing notes'))
    barrier=Barrier(8)
    def worker(_):
        barrier.wait()
        return create_app(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        apps=list(pool.map(worker,range(8)))
    for app in apps:
        client=app.test_client()
        assert client.get('/api/health').status_code==200
        rows=client.get('/api/devices').json
        if legacy:
            assert rows[0]['manual_code']==CODE and rows[0]['notes']=='Existing notes'
            assert rows[0]['revision']==1
        else:
            assert rows==[]
