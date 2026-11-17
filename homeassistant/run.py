"""Initialize the add-on's private volume, then run the shared app unprivileged."""
import json
import os
from pathlib import Path
import pwd


def addon_environment(options):
    help_enabled = options.get("home_assistant_help", False)
    if type(help_enabled) is not bool:
        raise ValueError("home_assistant_help must be true or false")
    return {"MATTERBASE_ADDON": "1", "MATTERBASE_HOME_ASSISTANT_HELP": "1" if help_enabled else "0",
            "DATA_DIR": "/data/matterbase", "PORT": "8000"}


def main():
    options_file = Path("/data/options.json")
    options = json.loads(options_file.read_text()) if options_file.exists() else {}
    if not isinstance(options, dict):
        raise ValueError("Add-on options must be an object")
    os.environ.update(addon_environment(options))
    account = pwd.getpwnam("app")
    directory = Path(os.environ["DATA_DIR"])
    if directory.is_symlink():
        raise ValueError("The inventory directory must not be a symbolic link")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chown(directory, account.pw_uid, account.pw_gid)
    os.chmod(directory, 0o700)
    for name in ("matterbase.sqlite3", "matterbase.sqlite3-wal", "matterbase.sqlite3-shm"):
        path = directory / name
        if path.is_symlink():
            raise ValueError("Inventory files must not be symbolic links")
        if path.exists():
            os.chown(path, account.pw_uid, account.pw_gid)
    os.setgroups([])
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.execvp("gunicorn", ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2",
                           "--timeout", "90", "--forwarded-allow-ips", "", "app:app"])


if __name__ == "__main__":
    main()
