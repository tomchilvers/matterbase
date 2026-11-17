import importlib.util
import json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]/'homeassistant_integration'
spec=importlib.util.spec_from_file_location('matterbase_connection',ROOT/'custom_components/matterbase/connection.py')
connection=importlib.util.module_from_spec(spec);spec.loader.exec_module(connection)

@pytest.mark.parametrize('url',['file:///etc/passwd','javascript:alert(1)','http://user:pass@host','https://host?secret=x','https://host/#secret','http://host:99999','http://host:0',None,'http://host/path with spaces','http://host/\\evil'])
def test_invalid_connector_urls(url):
    with pytest.raises(ValueError):connection.server_url(url)


def test_connector_metadata_and_url():
    assert connection.server_url(' https://matterbase.example.com/ ')=='https://matterbase.example.com'
    manifest=json.loads((ROOT/'custom_components/matterbase/manifest.json').read_text())
    assert manifest['config_flow'] and manifest['domain']=='matterbase' and manifest['requirements']==[]
    assert not list(ROOT.rglob('config.json'))
    assert not (ROOT/'repository.json').exists()
    assert (ROOT/'hacs.json').exists()
