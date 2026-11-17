"""Generate the native package from the shared UI and native-only adapters.

Vendored engines are committed, integrity-checked assets; installation never runs npm.
Use vendor_native.py to refresh them deliberately from its pinned registry lock.
"""
from pathlib import Path
import hashlib
import shutil

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'homeassistant_integration/custom_components/matterbase'


def build():
    output=PACKAGE/'web/native'
    target=output/'static';target.mkdir(parents=True,exist_ok=True)
    for path in (ROOT/'static').iterdir():
        if path.is_file() and path.name!='index.html':shutil.copyfile(path,target/path.name)
    for path in (ROOT/'homeassistant_integration/native_src').glob('*.mjs'):
        shutil.copyfile(path,target/path.name)
    html=(ROOT/'static/index.html').read_text().replace('href="./"','href="index.html"')
    html=html.replace('Stored on your server','Private inventory in Home Assistant')
    html=html.replace('<title>Matterbase · Your devices</title>','<title>Matterbase · Native inventory</title>')
    digest=hashlib.sha256(b''.join(path.read_bytes() for path in sorted(target.iterdir()) if path.is_file())).hexdigest()[:12]
    for name in ['style.css','app.js','transfers.js']:html=html.replace('static/'+name+'"','static/'+name+'?v='+digest+'"')
    (output/'index.html').write_text(html)
    for name in ['matter.py','text_recognition.py']:shutil.copyfile(ROOT/name,PACKAGE/name)
    return output


if __name__=='__main__':print('Generated native UI at',build())
