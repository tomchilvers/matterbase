import pytest
from app import create_app,embedding_origins


def test_explicit_origins_allow_embedding_without_changing_addon_access(tmp_path,monkeypatch):
    monkeypatch.setenv('MATTERBASE_FRAME_ANCESTORS','https://ha.example.com http://homeassistant.local:8123/')
    client=create_app(tmp_path).test_client()
    policy=client.get('/').headers['Content-Security-Policy']
    assert "frame-ancestors 'self' https://ha.example.com http://homeassistant.local:8123;" in policy
    assert '*' not in policy
    monkeypatch.setenv('MATTERBASE_ADDON','1')
    addon=create_app(tmp_path/'addon').test_client()
    assert addon.get('/').status_code==403
    response=addon.get('/',environ_overrides={'REMOTE_ADDR':'172.30.32.2'})
    assert "frame-ancestors 'self';" in response.headers['Content-Security-Policy']
    assert 'https://ha.example.com' not in response.headers['Content-Security-Policy']


@pytest.mark.parametrize('origin',['*','https://*.example.com',"'self'",'https://ha.example.com/path','https://user:password@ha.example.com','https://ha.example.com?x=1','https://ha.example.com;script-src','javascript:alert(1)','https://ha.example.com:99999','https://ha.example.com:0'])
def test_invalid_embedding_policy_fails_closed(origin):
    with pytest.raises(ValueError):embedding_origins(origin)


def test_origin_normalisation_and_ipv6():
    assert embedding_origins('https://HA.EXAMPLE.com/ https://ha.example.com http://[::1]:8123')==('https://ha.example.com','http://[::1]:8123')


def test_embedded_self_fetch_requires_origin_and_custom_header(tmp_path,monkeypatch):
    monkeypatch.setenv('MATTERBASE_FRAME_ANCESTORS','https://ha.example.com')
    client=create_app(tmp_path).test_client()
    payload={'code':'34970112332'}
    headers={'Sec-Fetch-Site':'cross-site','Origin':'http://localhost','X-Matterbase-Request':'1'}
    assert client.post('/api/validate',json=payload,headers=headers).status_code==200
    for missing in ('Origin','X-Matterbase-Request'):
        assert client.post('/api/validate',json=payload,headers={k:v for k,v in headers.items() if k!=missing}).status_code==403
    for foreign in ['https://evil.example','https://ha.example.com','null']:
        assert client.post('/api/validate',json=payload,headers={**headers,'Origin':foreign}).status_code==403
    response=client.options('/api/devices',headers={'Origin':'https://evil.example','Access-Control-Request-Headers':'X-Matterbase-Request'})
    assert 'Access-Control-Allow-Origin' not in response.headers


def test_default_standalone_cross_site_writes_stay_blocked(tmp_path,monkeypatch):
    monkeypatch.delenv('MATTERBASE_FRAME_ANCESTORS',raising=False)
    client=create_app(tmp_path).test_client()
    assert client.post('/api/validate',json={'code':'34970112332'},headers={'Sec-Fetch-Site':'cross-site','Origin':'http://localhost','X-Matterbase-Request':'1'}).status_code==403
    assert "frame-ancestors 'none'" in client.get('/').headers['Content-Security-Policy']


def test_import_and_edit_work_for_explicit_embedded_app(tmp_path,monkeypatch):
    monkeypatch.setenv('MATTERBASE_FRAME_ANCESTORS','https://ha.example.com')
    client=create_app(tmp_path).test_client()
    headers={'Sec-Fetch-Site':'cross-site','Origin':'http://localhost','X-Matterbase-Request':'1'}
    assert client.post('/api/devices',json={'devices':[{'manual_code':'34970112332','name':'Lamp'}]},headers=headers).status_code==201
    device=client.get('/api/devices').json[0]
    assert client.put(f'/api/devices/{device["id"]}',json={**device,'name':'Edited lamp'},headers=headers).status_code==200
    backup=client.get('/api/export').json
    preview=client.post('/api/import/preview',json={'backup':backup},headers=headers).json
    assert client.post('/api/import',json={'devices':[{**e,'action':'skip'} for e in preview['devices']]},headers=headers).json['skipped']==1
    assert client.delete(f'/api/devices/{device["id"]}',headers=headers).status_code==204
