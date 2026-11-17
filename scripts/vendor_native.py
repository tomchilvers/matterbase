"""Fetch pinned browser dependencies, verify npm integrity and vendor runtime assets."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'homeassistant_integration/custom_components/matterbase/web/native/vendor'
LOCK=ROOT/'homeassistant_integration/native_src/vendor-lock.json'


def vendor():
    DEST.mkdir(parents=True,exist_ok=True)
    packages={}
    for package in json.loads(LOCK.read_text()):
        content=urllib.request.urlopen(package['tarball'],timeout=60).read()
        algorithm,expected=package['integrity'].split('-',1)
        if base64.b64encode(hashlib.new(algorithm,content).digest()).decode()!=expected:raise ValueError('Package integrity mismatch')
        files={}
        with tarfile.open(fileobj=io.BytesIO(content),mode='r:gz') as archive:
            for member in archive.getmembers():
                if member.isfile() and member.name.startswith('package/') and '..' not in Path(member.name).parts:
                    files[member.name.removeprefix('package/')]=archive.extractfile(member).read()
        packages[package['name']]=files
    mappings={
        'zxing-wasm':{'dist/es/reader/index.js':'zxing/es/reader/index.js','dist/es/share.js':'zxing/es/share.js','dist/reader/zxing_reader.wasm':'zxing/reader/zxing_reader.wasm','LICENSE':'zxing/LICENSE'},
        'tesseract.js':{'dist/tesseract.min.js':'tesseract/tesseract.min.js','dist/worker.min.js':'tesseract/worker.min.js','LICENSE.md':'tesseract/LICENSE.md'},
        'tesseract.js-core':{name:'core/'+name for name in ['tesseract-core-lstm.wasm.js','tesseract-core-lstm.wasm','tesseract-core-simd-lstm.wasm.js','tesseract-core-simd-lstm.wasm','LICENSE']},
        '@tesseract.js-data/eng':{'4.0.0_best_int/eng.traineddata.gz':'lang/eng.traineddata.gz','README.md':'lang/README.md'},
        'qrcode-generator':{'dist/qrcode.mjs':'qrcode/qrcode.mjs'},
    }
    hashes={}
    for name,mapping in mappings.items():
        for source,target in mapping.items():
            content=packages[name][source];path=DEST/target;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            hashes[target]=hashlib.sha256(content).hexdigest()
    # Training data and ZXing-C++ use Apache 2.0; retain the full licence locally.
    apache=packages['tesseract.js-core']['LICENSE']
    (DEST/'lang/LICENSE').write_bytes(apache)
    (DEST/'zxing/ZXING_CPP_LICENSE').write_bytes(apache)
    mit=(ROOT/'homeassistant_integration/LICENSE').read_text().replace('2026 Tom Chilvers','2009 Kazuhiko Arase')
    (DEST/'qrcode/LICENSE').write_text(mit)
    (DEST/'ASSET_HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n')
    (DEST/'THIRD_PARTY_NOTICES.md').write_text('''# Browser scanning dependencies

Runtime assets are served locally by Home Assistant. No CDN is used.
Pinned versions, sources and npm integrity values: vendor-lock.json in native_src.

- zxing-wasm: MIT wrapper, ZXing-C++ WebAssembly under Apache 2.0.
- Tesseract.js and Tesseract.js-core: Apache 2.0.
- Tesseract English training data (tessdata / best_int): Apache 2.0.
- QR Code Generator, copyright 2009 Kazuhiko Arase: MIT.

The corresponding licence files are included alongside the assets.
''')
    print('Vendored',len(hashes),'local browser assets')


if __name__=='__main__':vendor()
