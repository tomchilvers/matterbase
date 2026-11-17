# Matterbase

A small, mobile-first home for Matter pairing codes. One Docker container, one SQLite database, no cloud services or API keys.

## Choose your installation

| Your setup | Install Matterbase |
| --- | --- |
| Home Assistant Container / Docker | Run the standalone image beside HA; install the Marketplace connector for a sidebar panel. [Container guide](docs/home-assistant-container.md) |
| Home Assistant OS | Install the app/add-on from this repository. Instructions below. |
| No Home Assistant | Use the standalone Docker / Dockhand setup below. |

Home Assistant Container has no app/add-on store, so the add-repository link only
works with Home Assistant OS. All three options use the same inventory format;
none automatically commissions devices or creates Home Assistant entities.

## Home Assistant Container / Docker

Use [compose.homeassistant.yaml](compose.homeassistant.yaml) in Dockhand. Set
`HOME_ASSISTANT_ORIGIN` to your Home Assistant browser URL, pull, and deploy.
Then install the [Marketplace/HACS connector](https://github.com/tomchilvers/matterbase-homeassistant)
using **Add from link**, and configure your Matterbase URL under **Devices & services**.
It adds a sidebar panel. Marketplace installs the connector; the Docker service
still runs separately. A Webpage dashboard is also available without the connector.

See the [Container guide](docs/home-assistant-container.md) for the complete setup,
HTTPS/camera requirements, existing-volume migration, and backups. Keep using
`:latest` for this deployment; the app/add-on image requires Supervisor ingress.

## Home Assistant app / add-on

Matterbase now also runs as an ingress app/add-on on Home Assistant OS. It uses
its own private inventory database; scanning, importing, and saving never add
entities or commission devices. Standalone Docker remains supported with the
same code and portable JSON format.

[Add the repository to Home Assistant](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Ftomchilvers%2Fmatterbase)

1. In the app/add-on store, open **Repositories** and add `https://github.com/tomchilvers/matterbase` (or use the link above).
2. Install **Matterbase**, start it, and select **Open Web UI**.
3. Optionally enable **Show in sidebar**.

No GitHub account, registry token, or local file copying is required. The image
supports AMD64 and AArch64. See the [add-on guide](homeassistant/matterbase/DOCS.md)
for migration, backups, camera access, and the fallback local-install bundle.
Home Assistant backups include the add-on’s separate data; cold backups briefly
stop it for a consistent database copy.

The optional **home_assistant_help** setting (off by default) adds per-device
instructions and a link to Home Assistant’s Matter setup. Commissioning still
happens explicitly in the Companion app; Matterbase does not send a code, create
an entity, or track pairing status. This follows the
[Home Assistant Matter pairing flow](https://www.home-assistant.io/integrations/matter/).
Standalone Docker can enable the same help using `MATTERBASE_HOME_ASSISTANT_HELP=1`.

## Run in Dockhand (prebuilt image)

GitHub Actions tests and builds the app on every push to `main`, then publishes **`ghcr.io/tomchilvers/matterbase:latest`** for Linux AMD64 and ARM64. Each architecture builds on a native runner and passes a container health check before the combined image tag is published. You can also run the workflow manually from the repository's **Actions** tab. Version tags such as `v1.0.0` publish `:1.0.0` and `:1.0`; builds also get a `:sha-<commit>` tag for pinning or rolling back. Only the default branch updates `:latest`.

The image is public; no registry login is needed. Create a stack named
**matterbase**, paste [compose.dockhand.yaml](compose.dockhand.yaml), and deploy.
Open `http://<server-ip>:8000` from your phone on the same network. Use HTTPS for
live camera access; photo upload and manual entry also work over HTTP.

For updates, pull the latest image and redeploy the stack in Dockhand. Publishing a new image does not restart your server's container automatically. The named data volume is retained. If migrating an existing Compose deployment, use its existing project/stack name so the volume is reused; check the volume mapping before deploying and do not run two containers against the same database at once.

Publishing uses GitHub Actions’ scoped `GITHUB_TOKEN`. Public source and images
do not expose your running app or inventory: those stay on your own server.

## Run from source

```sh
docker compose up --build -d
```

Open [http://localhost:8000](http://localhost:8000). From a phone on the same network, use `http://<server-ip>:8000`.

Live browser camera access requires **HTTPS** (except on localhost). Put the app behind your existing HTTPS reverse proxy for live scanning from a phone. Photo upload and manual entry also work over LAN HTTP; the photo picker can take a picture on supported mobile browsers. JPG, PNG, and WebP are supported; convert HEIC to JPG if your browser does not do that automatically.

## Import, export, and backups

Open **Import / Backup** from the device list. **Download JSON backup** exports the entire inventory, including names, brands, products, pairing codes, original QR payloads, notes, dates, colours, and icons. This also works with an empty inventory. Keep the downloaded file somewhere private: it contains pairing credentials.

Choose a Matterbase JSON backup (or paste its contents), then select **Preview import**. New devices default to Add; duplicates default to Skip. Each entry shows incoming details and offers an individual Add, Skip, or Overwrite choice. The final button states how many devices it will add and overwrite. Preview and Cancel do not change the database.

Restore merges into the inventory; it never removes devices absent from the backup. Overwrite restores the backup’s metadata, dates, and QR payload while retaining the local record ID. If another session changes a selected original or saves a new duplicate after preview, the entire import is rolled back and you must preview again. Older version 1 exports are supported. Files are limited to 16 MB and 10,000 records; invalid records or repeated codes reject the whole file.

For a full server backup, also back up the Docker volume containing `/data`. JSON backups are portable between installations and can be restored without Docker access. No Home Assistant connection or commissioning is involved.

## Use

- **Camera:** start the rear camera. Matter QR codes are collected continuously, including several in the same frame. The camera edge gives a brief green pulse and a capture count when new codes are found; repeated detections do not flash again. Brand and product recognition runs automatically on a captured frame after new QR codes are collected. Use **Capture text & codes** to stop and explicitly OCR another frame, including printed pairing codes. Reduced-motion settings replace the pulse with a steady confirmation border.
- **Photo:** upload a label or a photo of several labels. All detected Matter QR codes and valid printed codes are added to a review list. Unrelated QR codes are skipped.
- **Manual:** enter `XXXX-XXX-XXXX`, unformatted digits, or an `MT:` QR payload. Standard 11-digit and extended 21-digit manual codes are supported and validated, including their check digit.
- Review codes before saving. Confident brand and product suggestions are filled automatically. Product headings are matched to the QR codes beneath them, so a mixed photo can keep “KAJPLATS KIT” and “KAJPLATS” separate. Low-confidence OCR fragments, keyboard words, and packaging/legal text are filtered out of the short suggestion list; the original OCR text is available in a collapsed details section.
- Tap a product suggestion to fill remaining unnamed devices without replacing already matched or typed names. Batch fields apply across devices unless a field was edited individually. Manual changes, including cleared fields, take precedence over later recognition. Add an optional device name such as “Hallway lamp”.
- Previously saved brand/product names are offered as you type. When a QR has the same vendor and product IDs as saved devices, consistent saved names can fill missing details; conflicting saved names are left for review. All recognition runs locally and remains editable.
- **Colours and icons:** each code can have any label colour and a bulb, switch/remote, plug, or sensor icon. Change these in the scan review or **Edit** screen; select **None** / **No icon** to clear them. Colours and icons appear in the device list and can be searched by name (for example, “teal” or “switch”).
- When scanning a photo or camera frame, local image recognition looks for filled circular colour labels and common outlined bulb/switch markers beside each QR. It uses the QR's position and orientation to associate the marker with the correct row, including rotated photos, and compensates for a warm lighting cast on the paper. Suggestions are shown for review. Unknown artwork or conflicting nearby markers are left blank; plug and sensor icons are manual choices. Recognition works best on clear labels with markers immediately to the left or right of the QR. Printed codes found only by OCR still support manual colour/icon selection.
- Search by brand, product, device name, notes, or code. On desktop, select a device to see read-only details alongside the list (arrow keys also move between devices). On mobile, tap a row to expand it; one device opens at a time. Details include dates, brand, product, colour, icon, and notes. **Edit** opens the form in that panel; **Cancel** returns to the saved details. Use **Copy** for the pairing code and **Show pairing QR** to load the QR only when needed. Manual codes do not contain enough information to reconstruct the original QR payload.
- **Duplicates:** matching uses the canonical pairing code, so a QR and its printed manual code refer to the same stored record. A saved duplicate appears as **“This is a duplicate of ‘Hallway lamp’”**, with **Exclude from this scan** and **Overwrite original** choices. Several duplicates are shown inline, with an **Exclude all** option; no series of pop-ups interrupts the camera.
- Exclusion leaves the saved device unchanged and is remembered until you finish or cancel the current scan. Repeated readings of a new code already in the review list are kept once. Removing a review entry also excludes that code for the remainder of the scan.
- Choosing **Overwrite original** creates an editable draft, preserving the existing name/location, notes, and any details missing from the scan. A saved QR is retained on a manual-code rescan. The final save button explicitly lists the overwrites; the original record ID and creation date are retained. All duplicate choices must be resolved before saving.
- New devices and approved overwrites save together atomically. If another session adds the same code or edits an original after scanning, nothing in the batch is saved and a fresh duplicate choice is required. The same manual code can theoretically occur on separate physical devices; this app treats it as one stored credential.

Images are processed in memory on your server and are not retained. Original QR payloads and pairing codes are stored in SQLite. Nothing is seeded from example photos.

Existing databases automatically gain the colour/icon fields when the updated app starts. Saved pairing codes are preserved; existing records start with no colour or icon. Colours and icons are included in JSON exports.

## Storage and backup

The named `matterbase-data` Docker volume persists `/data/matterbase.sqlite3` across container restarts and image rebuilds. Do not run `docker compose down -v` unless you intend to delete your data.

**Import / Backup → Download JSON backup** downloads all device records. To take a complete restorable database backup, stop the service and copy the database from the volume (or use SQLite's online backup API). Restore by replacing the database in the stopped container's volume with your backup, preserving UID 10001 ownership. Alternatively, restore a JSON backup through **Import / Backup**, with a preview and explicit duplicate choices.

This is a single-household app without user accounts. Anyone who can reach it can read and change codes. Use it on a trusted network or behind an authenticated HTTPS reverse proxy; do not expose it directly to the public internet. The database and JSON exports contain pairing credentials in plain text.

```sh
docker compose logs -f
docker compose restart
docker compose down
```

## Development

Python 3.11+ and Tesseract OCR with English language data:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

`DATA_DIR` defaults to `./data`; `PORT` defaults to `8000`. The Docker image includes Tesseract and runs Gunicorn as a non-root user. Its builder stage compiles ZXing when a prebuilt wheel is unavailable, including Linux ARM64.

```sh
pip install pytest
python -m pytest -q
```

Recognition merge and edit-protection tests use Node.js 20+ with no npm dependencies:

```sh
node --test tests/*.test.mjs
```

The scanner uses [ZXing-C++](https://github.com/zxing-cpp/zxing-cpp/tree/master/wrappers/python), [Tesseract](https://github.com/tesseract-ocr/tesseract), and [OpenCV](https://opencv.org/) for local label marker recognition. Matter code parsing follows the [Project CHIP onboarding payload layout](https://github.com/project-chip/connectedhomeip/tree/master/src/setup_payload).

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET | `/api/devices` | List records |
| POST | `/api/devices` | Save new records and explicit overwrites atomically |
| PUT / DELETE | `/api/devices/<id>` | Update / delete a record |
| GET | `/api/devices/<id>/qr` | Render the original QR as PNG |
| POST | `/api/validate` | Validate `{ "code": "..." }` without saving |
| POST | `/api/scan` | Multipart `image` and optional `text=true/false` |
| GET | `/api/export` | Download JSON backup |
| POST | `/api/import/preview` | Validate a backup and preview duplicates |
| POST | `/api/import` | Import reviewed Add / Skip / Overwrite choices |

Upload limit: 16 MiB, 30 megapixels. QR decoding includes overlapping crops for small codes in wide photos. OCR is best effort, uses bounded recognition passes, and never silently saves recognised text.

`POST /api/devices` accepts `{ "devices": [...] }`. A new record has no overwrite fields. To explicitly overwrite, include `overwrite_id` and `expected_revision` from the saved record, alongside the same pairing code and the reviewed metadata. Missing overwrite metadata is preserved; explicit empty fields clear it. Successful responses include `saved`, `created`, and `updated` counts. Unapproved or stale duplicates return HTTP 409 with `conflicts` containing current saved records, when available. Reconfirm against the returned revision before retrying; never automatically replace an expected revision. No changes from a conflicting batch are saved.

## AI-assisted development

Matterbase was built with substantial AI assistance using OpenAI Codex. It is a
small personal project, not an official Home Assistant or IKEA product. Automated
tests cover the app and container flows, but that is not a security audit or a
promise that every phone, label, and Home Assistant setup has been tested.

Scanning runs locally using ZXing, Tesseract, and OpenCV. There is no AI API call
or cloud service in the scanning flow. Recognition can be wrong; review results
before saving. Please report bugs with synthetic examples rather than real pairing
codes or inventory backups.
