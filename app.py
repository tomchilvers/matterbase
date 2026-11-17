import json
import hashlib
from contextlib import closing
from io import BytesIO
from datetime import datetime, timezone
import os
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from PIL import Image
import zxingcpp

from matter import parse_code
from scanner import scan_image
from label_features import ICONS


def initialise_database(database):
    """Coordinate schema setup across workers, including WAL's initial lock.

    SQLite can return BUSY immediately when concurrent connections first switch
    journal modes, even with busy_timeout set. Retry the whole closed transaction.
    """
    deadline = time.monotonic() + 10
    while True:
        try:
            with closing(sqlite3.connect(database, timeout=2)) as conn, conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("""CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY, brand TEXT NOT NULL DEFAULT '', product TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
            manual_code TEXT NOT NULL UNIQUE, qr_payload TEXT NOT NULL DEFAULT '',
            vendor_id INTEGER, product_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            revision INTEGER NOT NULL DEFAULT 1
                )""")
                columns = {row[1] for row in conn.execute("PRAGMA table_info(devices)")}
                for column in ("color", "icon"):
                    if column not in columns:
                        conn.execute(f"ALTER TABLE devices ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
                if "revision" not in columns:
                    conn.execute("ALTER TABLE devices ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
            return
        except sqlite3.OperationalError as error:
            code = getattr(error, "sqlite_errorcode", 0) & 255
            if code not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or time.monotonic() >= deadline:
                raise
            time.sleep(.05)


def embedding_origins(value):
    """Accept exact HTTP(S) origins, never CSP wildcards or directives."""
    origins = []
    for origin in value.split():
        if len(origin) > 256 or not re.fullmatch(r"https?://(?:[a-zA-Z0-9.-]+|\[[a-fA-F0-9:]+\])(?::[0-9]+)?/?", origin):
            raise ValueError("MATTERBASE_FRAME_ANCESTORS must contain space-separated HTTP(S) origins, without paths or wildcards.")
        parsed = urlsplit(origin)
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("Invalid port in MATTERBASE_FRAME_ANCESTORS.")
        canonical = origin.rstrip("/").lower()
        if canonical not in origins:
            origins.append(canonical)
    if len(origins) > 10:
        raise ValueError("Allow at most 10 embedding origins.")
    return tuple(origins)


def create_app(data_dir=None):
    app = Flask(__name__, static_folder="static")
    app.config.update(MAX_CONTENT_LENGTH=16 * 1024 * 1024,
                      ADDON_MODE=os.environ.get("MATTERBASE_ADDON") == "1",
                      FRAME_ANCESTORS=embedding_origins(os.environ.get("MATTERBASE_FRAME_ANCESTORS", "")),
                      HOME_ASSISTANT_HELP=os.environ.get("MATTERBASE_HOME_ASSISTANT_HELP") == "1")
    directory = Path(data_dir or os.environ.get("DATA_DIR", "data"))
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "matterbase.sqlite3"
    initialise_database(database)

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(database, timeout=10)
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(error):
        connection = g.pop("db", None)
        if connection:
            connection.close()

    @app.before_request
    def ingress_access():
        if not app.config["ADDON_MODE"]:
            return None
        # Trust neither forwarding headers nor arbitrary peers. The documented
        # Supervisor ingress address is the only source of inventory requests.
        if request.remote_addr == "172.30.32.2":
            return None
        if request.remote_addr in ("127.0.0.1", "::1") and request.path == "/api/health" and request.method in ("GET", "HEAD"):
            return None
        return jsonify(error="Open Matterbase through Home Assistant ingress."), 403

    @app.before_request
    def same_origin():
        if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
            origin = request.headers.get("Origin")
            if origin and urlsplit(origin).netloc != request.host:
                return jsonify(error="Cross-origin writes are not allowed."), 403
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                # Browsers may classify even self-fetches inside a cross-site
                # iframe as cross-site. The app's custom header requires a CORS
                # preflight from any attacker origin; no CORS access is granted.
                embedded_self_request = (app.config["FRAME_ANCESTORS"] and origin and
                    urlsplit(origin).netloc == request.host and
                    request.headers.get("X-Matterbase-Request") == "1")
                if not embedded_self_request:
                    return jsonify(error="Cross-site requests are not allowed."), 403

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        frame_ancestors = "'self'" if app.config["ADDON_MODE"] else (
            "'self' " + " ".join(app.config["FRAME_ANCESTORS"]) if app.config["FRAME_ANCESTORS"] else "'none'")
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; "
            f"frame-ancestors {frame_ancestors}; base-uri 'none'; form-action 'self'"
        )
        if request.path == "/" or request.path.startswith(("/api/", "/static/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValueError)
    def validation(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        message = "Image is too large. Choose a file smaller than 16 MB." if error.code == 413 else error.description
        return jsonify(error=message), error.code

    @app.errorhandler(sqlite3.IntegrityError)
    def conflict(error):
        return jsonify(error="That pairing code is already saved. No changes were made."), 409

    # Fingerprint the entry points together so an updated page requests the
    # matching scripts/styles. Module dependencies also bypass browser caches.
    asset_version = hashlib.sha256(b"".join(path.read_bytes() for path in
        sorted(Path(app.static_folder).glob("*")) if path.is_file())).hexdigest()[:12]

    @app.get("/")
    def index():
        html = (Path(app.static_folder) / "index.html").read_text()
        html = re.sub(r'(static/[^"?]+\.(?:js|css))"', rf'\1?v={asset_version}"', html)
        html = html.replace('data-home-assistant-help="false"',
                            f'data-home-assistant-help="{str(app.config["HOME_ASSISTANT_HELP"]).lower()}"')
        return app.response_class(html, mimetype="text/html")

    @app.get("/api/health")
    def health():
        db().execute("SELECT 1")
        return jsonify(status="ok")

    @app.get("/api/devices")
    def devices():
        return jsonify([dict(row) for row in db().execute("SELECT * FROM devices ORDER BY id DESC")])

    def fields(item, existing=None):
        if not isinstance(item, dict):
            raise ValueError("Invalid device details.")
        result = {}
        for key, limit in (("brand", 120), ("product", 160), ("name", 160), ("notes", 2000)):
            value = item.get(key, "")
            if not isinstance(value, str) or len(value) > limit:
                raise ValueError(f"{key.capitalize()} must be text under {limit} characters.")
            result[key] = value.strip()
        for key in ("color", "icon"):
            value = item.get(key, existing[key] if existing else "")
            if not isinstance(value, str):
                raise ValueError(f"Invalid {key}.")
            value = value.strip().lower()
            if key == "color" and value and not re.fullmatch(r"#[0-9a-f]{6}", value):
                raise ValueError("Choose a valid colour in #RRGGBB format, or no colour.")
            if key == "icon" and value not in ICONS:
                raise ValueError("Choose a supported device icon.")
            result[key] = value
        parsed = parse_code(item.get("qr_payload") or item.get("manual_code", ""))
        if item.get("qr_payload") and item.get("manual_code"):
            manual = parse_code(item["manual_code"])["manual_code"]
            if manual != parsed["manual_code"]:
                raise ValueError("The QR payload and manual code do not match.")
        return {**result, **parsed}

    @app.post("/api/devices")
    def add():
        body = request.get_json()
        items = body.get("devices") if isinstance(body, dict) else None
        if not isinstance(items, list) or not 1 <= len(items) <= 100:
            raise ValueError("Add between 1 and 100 devices at a time.")
        # Lock and validate the entire batch before writing anything. An explicit
        # target ID + revision is required to overwrite a saved pairing code.
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            records, conflicts, seen = [], {}, set()
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Invalid device details.")
                record = fields(item)
                code = record["manual_code"]
                if code in seen:
                    return jsonify(error="The same pairing code appears twice in this batch. No changes were made."), 409
                seen.add(code)
                target = item.get("overwrite_id")
                if "overwrite_id" in item:
                    revision = item.get("expected_revision")
                    if type(target) is not int or target < 1 or type(revision) is not int or revision < 1:
                        raise ValueError("Overwriting requires a saved device ID and its current revision.")
                    original = conn.execute("SELECT * FROM devices WHERE id=?", (target,)).fetchone()
                    if not original:
                        return jsonify(error="The original device no longer exists. Exclude this entry and start a new scan to add it again. No changes were made."), 409
                    if original["manual_code"] != code:
                        raise ValueError("An overwrite must use the original device’s pairing code.")
                    if original["revision"] != revision:
                        conflicts[original["id"]] = dict(original)
                    # A manual-code rescan must not discard the saved QR payload;
                    # omitted metadata is preserved, while explicit blanks clear it.
                    record = fields({**dict(original), **item,
                                     "qr_payload": item.get("qr_payload") or original["qr_payload"]}, original)
                else:
                    original = conn.execute("SELECT * FROM devices WHERE manual_code=?", (code,)).fetchone()
                    if original:
                        conflicts[original["id"]] = dict(original)
                records.append((record, target))
            if conflicts:
                return jsonify(error="These codes are already saved, or an original changed since scanning. Choose Exclude or Overwrite again. No changes were made.",
                               conflicts=list(conflicts.values())), 409
            updated = 0
            for record, target in records:
                if target is not None:
                    conn.execute("UPDATE devices SET " + ",".join(f"{key}=?" for key in record) +
                                 ",revision=revision+1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                                 [*record.values(), target])
                    updated += 1
                    continue
                keys = list(record)
                conn.execute(f"INSERT INTO devices ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
                             [record[key] for key in keys])
        created = len(records) - updated
        return jsonify(saved=len(records), created=created, updated=updated), 201 if created else 200

    @app.put("/api/devices/<int:device_id>")
    def update(device_id):
        existing = db().execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
        if not existing:
            return jsonify(error="Device not found."), 404
        record = fields(request.get_json(), existing)
        with db() as conn:
            cursor = conn.execute("UPDATE devices SET " + ",".join(f"{key}=?" for key in record) +
                                  ",revision=revision+1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                                  [*record.values(), device_id])
            if not cursor.rowcount:
                return jsonify(error="Device not found."), 404
        return jsonify(saved=1)

    @app.delete("/api/devices/<int:device_id>")
    def delete(device_id):
        with db() as conn:
            cursor = conn.execute("DELETE FROM devices WHERE id=?", (device_id,))
        if not cursor.rowcount:
            return jsonify(error="Device not found."), 404
        return "", 204

    @app.get("/api/devices/<int:device_id>/qr")
    def qr_image(device_id):
        device = db().execute("SELECT qr_payload FROM devices WHERE id=?", (device_id,)).fetchone()
        if not device or not device["qr_payload"]:
            return jsonify(error="No original QR payload is saved for this device."), 404
        bitmap = memoryview(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.QRCode,
                            device["qr_payload"], width=240, height=240))
        image = Image.frombytes("L", (bitmap.shape[1], bitmap.shape[0]), bitmap.tobytes())
        output = BytesIO()
        image.save(output, format="PNG")
        return app.response_class(output.getvalue(), mimetype="image/png")

    @app.post("/api/scan")
    def scan():
        image = request.files.get("image")
        if not image:
            raise ValueError("Choose a photo first.")
        return jsonify(scan_image(image.read(), with_text=request.form.get("text", "true") == "true"))

    @app.post("/api/validate")
    def validate():
        body = request.get_json()
        return jsonify(parse_code(body.get("code") if isinstance(body, dict) else None))

    def import_records(items):
        if not isinstance(items, list) or len(items) > 10000:
            raise ValueError("Choose a backup containing up to 10,000 devices.")
        records, seen = [], set()
        for index, item in enumerate(items):
            try:
                record = fields(item)
                # Backups preserve text exactly, including note whitespace.
                for key in ("brand", "product", "name", "notes"):
                    record[key] = item.get(key, "")
                for key in ("created_at", "updated_at"):
                    value = item.get(key)
                    if value is not None:
                        if not isinstance(value, str) or len(value) > 40:
                            raise ValueError("Invalid backup date.")
                        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        if date.tzinfo is None:
                            raise ValueError("Backup dates must include a timezone.")
                        record[key] = value
                if record["manual_code"] in seen:
                    raise ValueError("The same pairing code appears more than once in this backup.")
                seen.add(record["manual_code"])
                records.append(record)
            except (ValueError, TypeError, AttributeError) as error:
                raise ValueError(f"Device {index + 1}: {error}") from error
        return records

    @app.post("/api/import/preview")
    def import_preview():
        body = request.get_json()
        backup = body.get("backup") if isinstance(body, dict) else None
        if not isinstance(backup, dict) or type(backup.get("version")) is not int or backup["version"] != 1:
            raise ValueError("Choose a supported Matterbase JSON backup (version 1).")
        records = import_records(backup.get("devices"))
        existing = {row["manual_code"]: dict(row) for row in db().execute("SELECT * FROM devices")}
        return jsonify(devices=[{"device": record, "original": existing.get(record["manual_code"])} for record in records])

    @app.post("/api/import")
    def import_inventory():
        body = request.get_json()
        items = body.get("devices") if isinstance(body, dict) else None
        if not isinstance(items, list):
            raise ValueError("Preview a backup before importing it.")
        records = import_records([item.get("device") if isinstance(item, dict) else None for item in items])
        created = updated = skipped = 0
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for item, record in zip(items, records):
                action = item.get("action")
                if action not in ("add", "skip", "overwrite"):
                    raise ValueError("Choose Add, Skip, or Overwrite for each device.")
                if action == "skip":
                    skipped += 1
                    continue
                original = conn.execute("SELECT * FROM devices WHERE manual_code=?", (record["manual_code"],)).fetchone()
                if action == "overwrite":
                    if (not original or type(item.get("expected_id")) is not int or
                            type(item.get("expected_revision")) is not int or
                            item["expected_id"] != original["id"] or item["expected_revision"] != original["revision"]):
                        raise ImportConflict("A saved device changed after preview. Preview the backup again; no changes were made.")
                    conn.execute("UPDATE devices SET " + ",".join(f"{key}=?" for key in record) +
                                 ",revision=revision+1 WHERE id=?", [*record.values(), original["id"]])
                    updated += 1
                else:
                    if original:
                        raise ImportConflict("A code was saved after preview. Preview the backup again; no changes were made.")
                    keys = list(record)
                    conn.execute(f"INSERT INTO devices ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", list(record.values()))
                    created += 1
        return jsonify(created=created, updated=updated, skipped=skipped)

    class ImportConflict(Exception):
        pass

    @app.errorhandler(ImportConflict)
    def import_conflict(error):
        return jsonify(error=str(error)), 409

    @app.get("/api/export")
    def export():
        rows = [dict(row) for row in db().execute("SELECT * FROM devices ORDER BY id")]
        return app.response_class(json.dumps({"version": 1, "exported_at": datetime.now(timezone.utc).isoformat(), "devices": rows}, indent=2),
                                  mimetype="application/json",
                                  headers={"Content-Disposition": 'attachment; filename="matterbase-backup.json"'})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), threaded=True)
