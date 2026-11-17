# Matterbase for Home Assistant Marketplace / HACS

A sidebar connector for [Matterbase](https://github.com/tomchilvers/matterbase), a
local inventory of Matter pairing codes. Works with Home Assistant Container and
Home Assistant OS. It creates no entities or devices and never commissions anything.

**This integration connects to an existing Matterbase server.** Marketplace/HACS
installs the connector; it does not install Docker services, Tesseract, or ZXing.
Your inventory stays in Matterbase's own database. Removing this integration does
not remove the inventory.

## Install

1. Deploy the standalone Matterbase image (`ghcr.io/tomchilvers/matterbase:latest`),
   following the [Container guide](https://github.com/tomchilvers/matterbase/blob/main/docs/home-assistant-container.md).
   Set `MATTERBASE_FRAME_ANCESTORS` to the Home Assistant URL you use in your browser.
   For example, `https://ha.example.com`. HTTPS Home Assistant needs HTTPS Matterbase.
2. In **Marketplace → Add from link**, use:
   `https://github.com/tomchilvers/matterbase-homeassistant`.
   In older HACS versions, add it as a custom repository of type **Integration**.
3. Install **Matterbase** and restart Home Assistant if prompted.
4. Go to **Settings → Devices & services → Add integration → Matterbase**.
5. Enter the Matterbase URL reachable from both Home Assistant and your browser.
   A **Matterbase** sidebar panel appears for administrators.

The sidebar supplies camera/clipboard iframe permissions and an **Open directly**
link for browsers that restrict embedded access. Use Photo/Manual if the live
camera is unavailable. A Home Assistant login does not secure the direct Matterbase
URL; keep it on your trusted network or behind your authenticated reverse proxy.

## Updates and removal

Marketplace/HACS updates this connector. Dockhand/Compose updates the independent
Matterbase server. Keep both current. To change the server URL, remove this
integration entry and add it again; this does not delete any inventory. Removing
an entry removes its sidebar panel.

## Development and scope

This is a personal project built with substantial AI assistance using OpenAI
Codex, not an official Home Assistant or IKEA product. The connector makes a
read-only health request during setup and embeds the configured web app. It
stores only that URL in Home Assistant; it does not copy pairing credentials into
entities, telemetry, or logs. Use synthetic data in bug reports.

The backend remains usable without Home Assistant. Scanning runs locally with
Tesseract, ZXing, and OpenCV; there is no cloud AI scanning service.
