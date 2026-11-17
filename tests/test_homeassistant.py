import importlib.util
import io
import json
from pathlib import Path
import re
import tarfile

import pytest
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.test import Client
from werkzeug.wrappers import Response
from app import create_app

ROOT=Path(__file__).resolve().parents[1]
PREFIX='/api/hassio_ingress/test-session/'

@pytest.fixture
def addon(monkeypatch,tmp_path):
    monkeypatch.setenv('MATTERBASE_ADDON','1')
    return create_app(tmp_path).test_client()


def test_addon_accepts_only_supervisor_and_loopback_health(addon):
    for remote in ['127.0.0.1','::1','172.30.32.8','192.168.1.1']:
        for path in ['/','/static/app.js','/api/devices','/api/export']:
            assert addon.get(path,environ_overrides={'REMOTE_ADDR':remote},headers={'X-Forwarded-For':'172.30.32.2'}).status_code==403
    assert addon.get('/api/health',environ_overrides={'REMOTE_ADDR':'127.0.0.1'}).status_code==200
    assert addon.post('/api/health',environ_overrides={'REMOTE_ADDR':'127.0.0.1'}).status_code==403
    assert addon.get('/api/health',environ_overrides={'REMOTE_ADDR':'172.30.32.8'}).status_code==403
    assert addon.get('/api/devices',environ_overrides={'REMOTE_ADDR':'172.30.32.2'}).json==[]


def test_ingress_allows_same_origin_framing_and_keeps_write_protection(addon):
    env={'REMOTE_ADDR':'172.30.32.2'}
    headers={'Host':'homeassistant.test:8123','X-Ingress-Path':PREFIX.rstrip('/')}
    assert "frame-ancestors 'self'" in addon.get('/',headers=headers,environ_overrides=env).headers['Content-Security-Policy']
    payload={'code':'34970112332'}
    assert addon.post('/api/validate',json=payload,headers={**headers,'Origin':'https://homeassistant.test:8123'},environ_overrides=env).status_code==200
    assert addon.post('/api/validate',json=payload,headers={**headers,'Origin':'https://evil.test'},environ_overrides=env).status_code==403
    assert addon.post('/api/validate',json=payload,headers={**headers,'Sec-Fetch-Site':'cross-site'},environ_overrides=env).status_code==403


def test_real_relative_urls_work_beneath_ingress_prefix(monkeypatch,tmp_path):
    monkeypatch.setenv('MATTERBASE_ADDON','1')
    app=create_app(tmp_path)
    client=Client(DispatcherMiddleware(Response('not found',404),{PREFIX.rstrip('/'):app}),Response)
    options={'environ_overrides':{'REMOTE_ADDR':'172.30.32.2'}}
    page=client.get(PREFIX,**options)
    assert page.status_code==200
    paths=re.findall(r'(?:src|href)="(static/[^" ]+)"',page.text)
    assert len(paths)==4
    for path in paths:
        assert client.get(PREFIX+path,**options).status_code==200
    assert client.post(PREFIX+'api/devices',json={'devices':[{'qr_payload':'MT:Y.K9042C00KA0648G00','name':'My lamp'}]},**options).status_code==201
    device=client.get(PREFIX+'api/devices',**options).json[0]
    assert client.get(PREFIX+f'api/devices/{device["id"]}/qr',**options).status_code==200
    backup=client.get(PREFIX+'api/export',**options).json
    assert backup['devices'][0]['name']=='My lamp'
    assert client.post(PREFIX+'api/import/preview',json={'backup':backup},**options).status_code==200


def test_standalone_has_no_homeassistant_dependency_or_help_by_default(tmp_path,monkeypatch):
    monkeypatch.delenv('MATTERBASE_ADDON',raising=False)
    monkeypatch.delenv('MATTERBASE_HOME_ASSISTANT_HELP',raising=False)
    client=create_app(tmp_path).test_client()
    page=client.get('/')
    assert page.status_code==200
    assert 'data-home-assistant-help="false"' in page.text
    assert "frame-ancestors 'none'" in page.headers['Content-Security-Policy']
    assert client.get('/api/devices').status_code==200
    monkeypatch.setenv('MATTERBASE_HOME_ASSISTANT_HELP','1')
    enabled=create_app(tmp_path).test_client().get('/')
    assert 'data-home-assistant-help="true"' in enabled.text


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded)
    return loaded


def test_addon_options_are_explicit_and_do_not_grant_api_access():
    launcher=module('homeassistant/run.py','addon_launcher')
    assert launcher.addon_environment({})['MATTERBASE_HOME_ASSISTANT_HELP']=='0'
    assert launcher.addon_environment({'home_assistant_help':True})['MATTERBASE_HOME_ASSISTANT_HELP']=='1'
    with pytest.raises(ValueError):launcher.addon_environment({'home_assistant_help':'false'})
    config=json.loads((ROOT/'homeassistant/matterbase/config.json').read_text())
    assert config['backup']=='cold' and config['ingress'] and config['ingress_port']==8000
    assert config['options']=={'home_assistant_help':False}
    assert not any(config.get(key) for key in ['ports','host_network','homeassistant_api','hassio_api','auth_api','docker_api','devices','map','privileged'])
    assert set(config['arch'])=={'aarch64','amd64'}


def test_local_bundle_is_self_contained_and_uses_the_same_core(tmp_path):
    package=module('scripts/package_addon.py','package_addon')
    destination=tmp_path/'addon.tar.gz'
    package.package(destination)
    with tarfile.open(destination) as archive:
        config=json.load(archive.extractfile('matterbase/config.json'))
        assert 'image' not in config
        for path in package.CORE_FILES:
            assert archive.extractfile('matterbase/'+path).read()==(ROOT/path).read_bytes()
        dockerfile=archive.extractfile('matterbase/Dockerfile').read().decode()
        assert dockerfile.rstrip().endswith('CMD ["python", "/app/addon_run.py"]')
        assert f'ARG ADDON_VERSION={config["version"]}' in dockerfile
        names=archive.getnames()
        assert all(name.startswith('matterbase/') and '..' not in name for name in names)
        assert not any('/data/' in name or '/.git/' in name or name.endswith('options.json') for name in names)
