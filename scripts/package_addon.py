"""Build a local-install add-on archive from the shared application source."""
import io
import json
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
CORE_FILES = ("app.py", "matter.py", "scanner.py", "label_features.py", "text_recognition.py", "requirements.txt")


def package(destination):
    config = json.loads((ROOT / "homeassistant/matterbase/config.json").read_text())
    config.pop("image")  # Local installs build the shared source, without GHCR credentials.
    dockerfile = (ROOT / "Dockerfile").read_text().split("# Keep the default docker build / Compose target standalone", 1)[0]
    files = {name: (ROOT / name).read_bytes() for name in CORE_FILES}
    files.update({f"static/{p.name}": p.read_bytes() for p in sorted((ROOT / "static").iterdir()) if p.is_file()})
    files.update({"Dockerfile": dockerfile.encode(), "config.json": (json.dumps(config, indent=2) + "\n").encode(),
                  "homeassistant/run.py": (ROOT / "homeassistant/run.py").read_bytes()})
    for name in ("README.md", "DOCS.md", "CHANGELOG.md"):
        files[name] = (ROOT / "homeassistant/matterbase" / name).read_bytes()
    with tarfile.open(destination, "w:gz") as archive:
        for name, content in sorted(files.items()):
            info = tarfile.TarInfo(f"matterbase/{name}")
            info.size, info.mode = len(content), 0o644
            archive.addfile(info, io.BytesIO(content))
    return config["version"]


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/matterbase-homeassistant.tar.gz")
    print(f"Packaged Matterbase {package(output)} at {output}")
