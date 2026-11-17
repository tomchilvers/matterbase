# Matterbase for Home Assistant

## Install from the repository

Requires Home Assistant OS with the app/add-on store. Home Assistant Container
users should use the [Container deployment guide](https://github.com/tomchilvers/matterbase/blob/main/docs/home-assistant-container.md), including the optional Webpage dashboard.

1. Open **Settings → Apps → Install app** (or the Add-on Store on older versions).
2. Open the top-right menu, select **Repositories**, and add:
   `https://github.com/tomchilvers/matterbase`.
3. Find **Matterbase**, select **Install**, then **Start**.
4. Select **Open Web UI**. Optionally enable **Show in sidebar**.

[Add the repository](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Ftomchilvers%2Fmatterbase)

The repository and images are public. No GitHub token, registry login, or file
copying is needed. Supervisor pulls `ghcr.io/tomchilvers/matterbase:1.0.0-ha.3`
for AMD64 or AArch64. Update through the app/add-on store when a new version appears.

## Local installation (fallback)

Download **matterbase-homeassistant** from a successful GitHub Actions run, or
run `python3 scripts/package_addon.py` from a checkout. Extract the resulting
`matterbase-homeassistant.tar.gz` into the local apps directory so it contains
`/addons/matterbase/config.json` and `/addons/matterbase/Dockerfile` (the path as
exposed by Terminal & SSH or Samba). Reload the store, then install **Matterbase**
under Local apps / Local add-ons. This builds the same source locally.

The bundle contains source only, not inventory or photos. Keep the folder name
`matterbase` when updating a local install so its data volume is retained.

## Your inventory stays separate

Data is stored in the add-on's private `/data/matterbase/` directory. It does not
read or alter Home Assistant's device registry, entities, configuration, or Matter
Server database. It does not request a Home Assistant, Supervisor, or Docker API
permission, Bluetooth access, or host networking.

Standalone Docker continues to run exactly as before, with its own database.
To move an inventory, download a JSON backup from one installation and import it
into the other. Preview first; duplicates default to Skip. The two installations
are independent and do not synchronise automatically.

## Optional pairing help

The **home_assistant_help** configuration option defaults to **false**. Turn it on
and restart the add-on to show **Add to Home Assistant (optional)** in each saved
device's details. Standalone Docker can enable the same help with
`MATTERBASE_HOME_ASSISTANT_HELP=1`.

This expands instructions and offers a link to Home Assistant's Matter setup.
Use **Copy** for the stored code, then follow the Companion app's normal Matter
pairing flow on your phone. The device must be in pairing mode. Devices already
paired to another controller normally need a fresh sharing code from that
controller. Matterbase never commissions anything or claims pairing succeeded.
It does not send pairing codes to Home Assistant or to the external setup link.

Reference: https://www.home-assistant.io/integrations/matter/

## Backups and restore

Include Matterbase in Home Assistant's backups. It uses **cold** backups: Home
Assistant stops the add-on while copying its private data, then restarts it. This
keeps the SQLite database and WAL consistent. Restore the Matterbase app and data
from that backup using Home Assistant's restore UI.

**Import / Backup → Download JSON backup** also provides a portable inventory
backup usable in either deployment. Store backups privately: they contain pairing
credentials. Import merges and never removes inventory entries absent from the file.

## Access and camera

The add-on accepts inventory requests only from Home Assistant's ingress proxy.
It publishes no host port. Only the local health endpoint is available to loopback
health checks. Ingress can embed the UI within the same Home Assistant origin;
standalone retains its existing framing restrictions and same-origin checks.

Use Home Assistant over HTTPS for the live camera. Camera availability also depends
on the browser/Companion app webview and its iframe permission policy. If the camera
is unavailable, use **Photo** to take/upload a picture, or enter a printed code.

## Developer verification

The shared Python/Node suites cover standalone behavior, ingress access controls,
relative asset/API/QR URLs, options, and portable packaging. CI builds and smoke-tests
both standalone and add-on images on native AMD64/ARM64 runners, including a
simulated trusted ingress proxy and a fresh root-owned data volume.

A real Home Assistant OS installation, sidebar behavior, platform backups/restores,
and mobile camera permissions still need a host test; simulated ingress is not a
substitute for that final installation check.

## Releases

The published add-on version is taken from `config.json`; bump it for an add-on
release. CI never moves an existing version tag. `ha-latest` and `ha-sha-<commit>`
are development tags; Supervisor installs the configured version. Standalone
`:latest` retains its existing independent update behavior.

## About this project

Matterbase is a personal project developed with substantial AI assistance from
OpenAI Codex. It is not an official Home Assistant app. Recognition runs locally;
there is no cloud AI service in the scanning flow. Review recognised values before
saving and avoid including real pairing credentials in bug reports.
