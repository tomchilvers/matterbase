import io
import sqlite3

import pytest
import zxingcpp
from PIL import Image, ImageDraw

from app import create_app
from scanner import scan_image

PAYLOAD = 'MT:Y.K9042C00KA0648G00'


def label_image(marker):
    bitmap = memoryview(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.QRCode, PAYLOAD, width=160, height=160))
    qr = Image.frombytes('L', (bitmap.shape[1], bitmap.shape[0]), bitmap.tobytes()).resize((160, 160), Image.Resampling.NEAREST)
    image = Image.new('RGB', (700, 500), 'white')
    image.paste(qr, (360, 180))
    draw = ImageDraw.Draw(image)
    if marker == 'color':
        draw.ellipse((170, 190, 300, 320), fill='#cc7149')
    elif marker == 'bulb':
        draw.ellipse((210, 210, 280, 290), outline='black', width=6)
        draw.line((230, 300, 260, 300), fill='black', width=6)
        draw.line((235, 310, 255, 310), fill='black', width=6)
    elif marker == 'switch':
        draw.rounded_rectangle((210, 190, 280, 320), radius=34, outline='black', width=6)
        draw.ellipse((237, 207, 253, 223), outline='black', width=3)
    elif marker == 'unknown':
        draw.polygon([(210, 195), (280, 250), (210, 320)], outline='black', width=6)
    return image


@pytest.mark.parametrize('marker', ['color', 'bulb', 'switch', 'unknown'])
@pytest.mark.parametrize('angle', [0, 90, 180, 270])
def test_scanned_markers_follow_qr_orientation(marker, angle):
    image = label_image(marker).rotate(angle, expand=True)
    output = io.BytesIO()
    image.save(output, format='PNG')
    codes = scan_image(output.getvalue(), with_text=False)['codes']
    assert len(codes) == 1
    code = codes[0]
    assert code['icon'] == (marker if marker in ('bulb', 'switch') else '')
    assert bool(code['color']) == (marker == 'color')


def test_remote_colour_is_not_assigned_to_qr():
    image = label_image('unknown')
    ImageDraw.Draw(image).ellipse((5, 5, 100, 100), fill='red')
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    code = scan_image(stream.getvalue(), False)['codes'][0]
    assert code['color'] == ''
    assert code['icon'] == ''


def test_tiled_detection_uses_full_image_coordinates(monkeypatch):
    import scanner
    image = Image.new('RGB', (1200, 800), 'white')
    image.paste(label_image('switch'), (400, 280))
    original = zxingcpp.read_barcodes
    calls = 0

    def tiled_reader(view, **kwargs):
        nonlocal calls
        calls += 1
        # Force recovery from an offset tile, where the QR has local coordinates.
        return original(view, **kwargs) if calls == 5 else []

    monkeypatch.setattr(scanner.zxingcpp, 'read_barcodes', tiled_reader)
    monkeypatch.setattr(scanner.shutil, 'which', lambda command: None)
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    codes = scanner.scan_image(stream.getvalue(), True)['codes']
    assert len(codes) == 1 and codes[0]['icon'] == 'switch'


def test_existing_database_migrates_without_losing_credentials(tmp_path):
    path = tmp_path / 'matterbase.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE devices (id INTEGER PRIMARY KEY, brand TEXT DEFAULT '',
            product TEXT DEFAULT '', name TEXT DEFAULT '', notes TEXT DEFAULT '',
            manual_code TEXT UNIQUE, qr_payload TEXT DEFAULT '', vendor_id INTEGER,
            product_id INTEGER, created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '')""")
        db.execute("INSERT INTO devices (manual_code, name) VALUES ('34970112332', 'Existing lamp')")
    client = create_app(tmp_path).test_client()
    record = client.get('/api/devices').json[0]
    assert record['name'] == 'Existing lamp'
    assert record['color'] == record['icon'] == ''
    # Starting another worker/process must not repeat or break the migration.
    assert create_app(tmp_path).test_client().get('/api/devices').json == [record]


def test_manual_markers_persist_edit_clear_and_export(tmp_path):
    client = create_app(tmp_path).test_client()
    record = {'qr_payload': PAYLOAD, 'color': '#CC7149', 'icon': 'bulb'}
    assert client.post('/api/devices', json={'devices':[record]}).status_code == 201
    device = client.get('/api/devices').json[0]
    assert device['color'] == '#cc7149'
    assert device['icon'] == 'bulb'
    # Older clients that don't know these fields preserve them on update.
    older = {key:value for key,value in device.items() if key not in ('color','icon')}
    assert client.put(f"/api/devices/{device['id']}", json=older).status_code == 200
    assert client.get('/api/devices').json[0]['icon'] == 'bulb'
    device.update(color='#568bc5', icon='switch')
    assert client.put(f"/api/devices/{device['id']}", json=device).status_code == 200
    export = client.get('/api/export').json['devices'][0]
    assert export['color'] == '#568bc5' and export['icon'] == 'switch'
    device.update(color='', icon='')
    client.put(f"/api/devices/{device['id']}", json=device)
    assert create_app(tmp_path).test_client().get('/api/devices').json[0]['color'] == ''


@pytest.mark.parametrize('field,value', [('color','red'),('color','#123'),('color',False),('icon','<script>'),('icon',2)])
def test_invalid_marker_values_rejected(tmp_path,field,value):
    client = create_app(tmp_path).test_client()
    response = client.post('/api/devices', json={'devices':[{'qr_payload':PAYLOAD,field:value}]})
    assert response.status_code == 400
    assert client.get('/api/devices').json == []
