"""Run from the simulated Supervisor address against the add-on container."""
import json
from urllib.request import Request, urlopen

BASE = "http://172.30.32.10:8000/"
HEADERS = {"Host": "homeassistant.test:8123", "X-Ingress-Path": "/api/hassio_ingress/test-session/"}


def call(path, payload=None):
    headers = {**HEADERS}
    body = None
    if payload is not None:
        headers.update({"Content-Type": "application/json", "Origin": "http://homeassistant.test:8123"})
        body = json.dumps(payload).encode()
    with urlopen(Request(BASE + path, data=body, headers=headers), timeout=30) as response:
        return response.read(), response.headers


page, headers = call("")
assert b'src="static/app.js?v=' in page
assert b'data-home-assistant-help="false"' in page
assert "frame-ancestors 'self'" in headers["Content-Security-Policy"]
call("static/app.js")
call("static/inventory.mjs")
assert json.loads(call("api/devices")[0]) == []
call("api/devices", {"devices": [{"qr_payload": "MT:Y.K9042C00KA0648G00", "name": "Smoke-test lamp"}]})
backup = json.loads(call("api/export")[0])
assert backup["devices"][0]["name"] == "Smoke-test lamp"
call(f'api/devices/{backup["devices"][0]["id"]}/qr')
preview = json.loads(call("api/import/preview", {"backup": backup})[0])
assert preview["devices"][0]["original"]["name"] == "Smoke-test lamp"
result = json.loads(call("api/import", {"devices": [{**entry, "action": "skip"} for entry in preview["devices"]]})[0])
assert result == {"created": 0, "updated": 0, "skipped": 1}
print("Trusted ingress, assets, same-origin writes, QR, export, and import passed")
