import io
import json
import pytest
from PIL import Image
from app import create_app
from matter import parse_code, checksum
from scanner import scan_image, extract_text_codes

PAYLOAD = "MT:EX7A00O6148-.548G00"
CODE = "00054912336"

@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    app.config['TESTING'] = True
    return app.test_client()

def test_reference_qr_and_manual_are_same():
    qr = parse_code(PAYLOAD)
    assert qr['manual_code'] == CODE
    assert qr['vendor_id'] == 4476
    assert parse_code('0005-491-2336')['manual_code'] == CODE

@pytest.mark.parametrize('value', ['0005-491-2337', '12345678901', 'MT:AAAA', 'MT:$$$$$$$$$$$$$$$$$$$', None, '1' * 10000])
def test_reject_invalid_codes(value):
    with pytest.raises(ValueError):
        parse_code(value)

def test_known_standard_matter_payload():
    assert parse_code('MT:Y.K9042C00KA0648G00')['manual_code'] == '34970112332'

def test_crud_duplicate_and_transaction(client):
    batch = {'devices': [{'qr_payload': PAYLOAD, 'brand':'IKEA','product':'KAJPLATS'}]}
    assert client.post('/api/devices',json=batch).status_code == 201
    device = client.get('/api/devices').json[0]
    assert device['manual_code'] == CODE
    assert client.post('/api/devices',json={'devices':[{'manual_code':'1497-021-2332'},{'manual_code':CODE}]}).status_code == 409
    assert len(client.get('/api/devices').json) == 1
    device['name'] = 'Hallway lamp'
    assert client.put(f"/api/devices/{device['id']}",json=device).status_code == 200
    assert client.get('/api/devices').json[0]['name'] == 'Hallway lamp'
    exported = client.get('/api/export')
    assert json.loads(exported.data)['devices'][0]['qr_payload'] == PAYLOAD
    assert client.delete(f"/api/devices/{device['id']}").status_code == 204
    assert client.get('/api/devices').json == []

def test_validation_no_write(client):
    assert client.post('/api/validate',json={'code':CODE}).json['manual_code'] == CODE
    assert client.get('/api/devices').json == []

def test_saved_qr_can_be_scanned_again(client):
    client.post('/api/devices',json={'devices':[{'qr_payload':PAYLOAD}]})
    device = client.get('/api/devices').json[0]
    png = client.get(f"/api/devices/{device['id']}/qr")
    assert png.content_type == 'image/png'
    assert scan_image(png.data,False)['codes'][0]['qr_payload'] == PAYLOAD

def test_manual_device_has_no_invented_qr(client):
    client.post('/api/devices',json={'devices':[{'manual_code':CODE}]})
    device = client.get('/api/devices').json[0]
    assert client.get(f"/api/devices/{device['id']}/qr").status_code == 404

def test_mismatch_rejected(client):
    response = client.post('/api/devices',json={'devices':[{'qr_payload':PAYLOAD,'manual_code':'14970212332'}]})
    assert response.status_code == 400

def test_persistence(tmp_path):
    one = create_app(tmp_path).test_client()
    one.post('/api/devices',json={'devices':[{'manual_code':CODE}]})
    two = create_app(tmp_path).test_client()
    assert two.get('/api/devices').json[0]['manual_code'] == CODE

def test_scan_bad_image(client):
    response = client.post('/api/scan',data={'image':(io.BytesIO(b'not an image'),'bad.jpg')})
    assert response.status_code == 400

def test_empty_image():
    stream = io.BytesIO()
    Image.new('RGB',(100,100),'white').save(stream,format='PNG')
    assert scan_image(stream.getvalue(),False)['codes'] == []

def test_ocr_code_filtering():
    codes = extract_text_codes('IKEA KAJPLATS 0005-491-2336 0005-491-2337 © 2025 AA-2595622-5')
    assert [c['manual_code'] for c in codes] == [CODE]

def test_cross_origin_blocked(client):
    assert client.post('/api/validate',json={'code':CODE},headers={'Origin':'https://other.example'}).status_code == 403

def test_payload_validation(client):
    assert client.post('/api/devices',json={'devices':[{'manual_code':CODE,'brand':3}]}).status_code == 400
    assert client.post('/api/devices',json={'devices':[]}).status_code == 400
    assert client.post('/api/validate',json={}).status_code == 400
    assert client.post('/api/scan',data={}).status_code == 400

def test_nonstandard_flow_roundtrip():
    # Construct a custom-flow QR bit payload; its manual code includes VID/PID.
    bits = (4476 << 3) | (123 << 19) | (2 << 35) | (2 << 37) | (3840 << 45) | (20202021 << 57)
    data = bits.to_bytes(11,'little'); alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-.'
    encoded = ''
    for offset in range(0,11,3):
        chunk = data[offset:offset+3]; n = int.from_bytes(chunk,'little')
        for _ in range({1:2,2:4,3:5}[len(chunk)]):
            encoded += alphabet[n % 38]; n //= 38
    parsed = parse_code('MT:' + encoded)
    assert len(parsed['manual_code']) == 21
    assert parse_code(parsed['manual_code'])['manual_code'] == parsed['manual_code']


def test_release_assets_are_fingerprinted_and_not_stored(client):
    import re
    page=client.get('/')
    assert page.headers['Cache-Control']=='no-store'
    assets=re.findall(r'(static\/[^"?]+\.(?:js|css)\?v=[0-9a-f]{12})',page.text)
    assert len(assets)==3
    for asset in assets+['/static/recognition.mjs','/static/duplicates.mjs']:
        response=client.get('/'+asset.lstrip('/'))
        assert response.status_code==200
        assert response.headers['Cache-Control']=='no-store'
