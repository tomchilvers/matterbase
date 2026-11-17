# Matterbase for Home Assistant Marketplace / HACS

A native, private inventory of Matter pairing codes inside Home Assistant. **No separate Matterbase container or server is needed.** Works with Home Assistant Container and Home Assistant OS.

## Install

1. In **Marketplace → Add from link**, enter `https://github.com/tomchilvers/matterbase-homeassistant`. Older HACS: add a custom repository of type **Integration**.
2. Install Matterbase and restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → Matterbase**.
4. Open **Matterbase** in the sidebar as an administrator.

Scan multiple QR codes from photos or the camera, read brand/product text, choose label colours and icons, or enter codes manually. Review detected details before saving. Duplicates require an explicit Exclude or Overwrite choice. Desktop uses a split view; mobile uses expandable rows. Pairing QR codes appear only on request.

All QR/OCR engines and English language data are bundled locally. Photos are processed in your browser; images are not uploaded to Home Assistant or a cloud service. Loading OCR can take a moment on the first scan. Live camera access requires HTTPS (or localhost), browser permission, and a supported browser. Photo and manual input remain available. Colour/icon suggestions are approximate and editable.

The panel follows Home Assistant’s light/dark theme and updates when you change it. Standalone Docker follows your device’s colour preference.

## Inventory and backups

Inventory is stored separately from Home Assistant entities and devices in the private `.storage/matterbase.inventory` file. The API and sidebar require an administrator login. No devices are automatically commissioned, no entities are created, and no pairing credentials are placed in entity states or logs.

Use **Import / Backup** for a portable version-1 JSON backup. The same JSON format works in standalone Docker. Keep backups private: they contain pairing credentials. Include Home Assistant's configuration directory in server backups. Removing this integration entry removes the panel but retains the inventory file; adding it again restores access.

Optional Home Assistant pairing instructions can be enabled in the integration options. Pairing itself remains a separate, deliberate Home Assistant action.

## Migrating from the version-1 connector

Existing connector entries continue opening their external Matterbase server; upgrading does not silently move or delete data.

1. Export a JSON backup from your existing Matterbase server.
2. Remove the existing Matterbase integration entry in Devices & services.
3. Add Matterbase again to create a native inventory.
4. Import the JSON backup, review conflicts, and verify the saved devices.
5. Keep your old backup and Docker volume until you have verified the migration. You may then stop the separate Matterbase container.

Native mode needs no Matterbase URL, reverse proxy, or `MATTERBASE_FRAME_ANCESTORS` setting. Standalone [Matterbase Docker](https://github.com/tomchilvers/matterbase) remains supported independently. Existing external connector entries still require their previous embedding configuration.

## Development

This personal project was built with substantial AI assistance using OpenAI Codex. It is not an official Home Assistant, Matter, or IKEA product. Recognition uses local ZXing and Tesseract, not cloud AI.

The integration is MIT licensed; bundled dependencies retain their own licences in `custom_components/matterbase/web/native/vendor/`. This does not relicense the separate Matterbase server. Frontend and pure recognition sources are shared with the main repository; generated native assets are committed so Marketplace installations need no build tools.
