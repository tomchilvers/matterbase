# For a fully native installation with no separate service, install the
[Marketplace integration](https://github.com/tomchilvers/matterbase-homeassistant).
This guide covers the optional **independent Docker deployment** and embedding it
in Home Assistant. Home Assistant Container has no Supervisor/add-on store; the
native Marketplace integration works without Supervisor.

## 1. Deploy Matterbase beside Home Assistant

In Dockhand, use [compose.homeassistant.yaml](../compose.homeassistant.yaml) in a
stack named **matterbase**. Set the stack environment variable
`MATTERBASE_FRAME_ANCESTORS` to the exact Home Assistant URL you use in your browser:

```text
MATTERBASE_FRAME_ANCESTORS=http://192.0.2.10:8123
```

The address above is an example: replace it with your actual server address.
For HTTPS, use the HTTPS origin, such as `https://ha.example.com`.
No path, query, or wildcard belongs in an origin. Several origins can be separated
by spaces if you use both a local URL and a remote URL.

If you already have a Matterbase stack, keep its name and existing volume mapping.
You can simply add these two environment variables to your current service:

```yaml
environment:
  DATA_DIR: /data
  MATTERBASE_HOME_ASSISTANT_HELP: "1"
  MATTERBASE_FRAME_ANCESTORS: "http://192.0.2.10:8123"
```

All three Compose files now pass this setting through. The Home Assistant-specific
file requires a value; ordinary standalone files leave embedding off when it is
blank. Existing `HOME_ASSISTANT_ORIGIN` settings remain supported as a fallback,
and an explicit `MATTERBASE_FRAME_ANCESTORS` value takes precedence.

For command-line Compose, copy `.env.example` to `.env` beside the Compose file and
set the value there. In Dockhand, use its **stack environment** editor (or put the
actual URL directly in the service's `environment` section).

If setup says **“The server blocks embedding”**, pull the latest image and
**redeploy/recreate the existing container** after setting this variable. A simple
restart keeps the old environment. Retry integration setup after the container is
healthy. Keep the existing stack name and data volume.

Pull the latest image and redeploy. Keep using the standalone `:latest` image,
not the `-ha.*` add-on images: those accept only Supervisor ingress requests.
Do not run a second container against the same SQLite data volume.

Open Matterbase directly at `http://YOUR_SERVER:8000/` and check it works first.
No shared Docker network, Home Assistant volume mount, or host networking is needed.

## 2. Display the independent Docker app

Existing version-1 Marketplace connector entries continue to work after upgrading.
New version-2 integration entries create a native inventory, rather than asking for
an external server URL. To move from Docker to native, follow the JSON migration
instructions in the [integration README](https://github.com/tomchilvers/matterbase-homeassistant).
For a new sidebar showing your independent Docker server, use a Webpage dashboard:

In Home Assistant, go to **Settings → Dashboards → Add dashboard**, choose
**Webpage**, and set:

- Title: **Matterbase**
- Icon: **mdi:qrcode-scan**
- URL: the Matterbase address you can open from your browser or phone
- Enable **Show in sidebar**

Use a browser-reachable address such as your server's LAN address or HTTPS domain,
not a Docker-only hostname like `http://matterbase:8000`.

Alternatively, add a Webpage card to an existing dashboard:

```yaml
type: iframe
url: https://matterbase.example.com/
aspect_ratio: 100%
allow: "camera; clipboard-write; fullscreen"
```

Replace the example URL. For a full-page view, put the card in a Panel view.
The old `panel_iframe` configuration is not needed.

Reference: [Webpage dashboards](https://www.home-assistant.io/dashboards/dashboards/#webpage-dashboard)
and [Webpage cards](https://www.home-assistant.io/dashboards/iframe/).

## HTTPS, camera, and access

If Home Assistant uses HTTPS, Matterbase must also use HTTPS to be embedded;
browsers block an HTTP frame inside an HTTPS page. Use your existing reverse proxy
and a dedicated Matterbase hostname. Live camera scanning also needs HTTPS, plus
camera permission on the iframe. A Webpage card's `allow` option above can delegate
camera and clipboard permission; the browser/Companion app may still limit them.
Open Matterbase directly if camera or clipboard access is unavailable in the frame.
Photo upload and manual input remain available.

`MATTERBASE_FRAME_ANCESTORS` controls which sites may embed Matterbase. It does not
provide authentication or grant Home Assistant's login to the Matterbase service.
Keep direct access on your trusted network or behind an authenticated HTTPS proxy.
No CORS access is enabled; inventory writes still require the app's own origin.
Leaving this variable unset keeps standalone framing disabled. The Home Assistant
OS add-on retains its separate Supervisor-only access control.

## Inventory, backups, and optional pairing

The database stays in Matterbase's own Docker volume. Import/export and QR reveal
work in either deployment, and no entities or devices are created automatically.
`MATTERBASE_HOME_ASSISTANT_HELP=1` shows optional Companion app pairing instructions.
Pairing still requires your explicit action in Home Assistant's normal Matter flow.

Home Assistant Container backups do not automatically include this separate
Matterbase volume. Download a JSON inventory backup through **Import / Backup**,
or stop Matterbase and back up its Docker data volume. Restore/import uses the
same review and duplicate choices as standalone Docker.
