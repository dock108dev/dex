"""Open the running Dex, or start its existing installation without key prompts."""

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

PYTHON = Path(sys.executable)
ROOT = (
    Path(os.environ.get("DEX_APP_ROOT", Path(__file__).resolve().parents[1] / ".local/customer"))
    .expanduser()
    .resolve()
)


def main():
    listener = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-tiTCP:8011", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    if listener.returncode not in (0, 1):
        raise SystemExit("Could not check whether Dex is already running.")
    if listener.stdout.strip():
        webbrowser.open("http://127.0.0.1:8011/", new=0)
        return
    if not (ROOT / "B1_ISOLATED").is_file() or not (ROOT / "inventory.db").is_file():
        raise SystemExit("The existing Dex installation is unavailable.")
    os.environ["DEX_PROFILE"] = "local"
    # The installed app reads the configured project .env. Do not inherit stale key
    # overrides from the parent Terminal after the user edits that file.
    for name in ("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_DELIVERY_POSTAL_CODE"):
        os.environ.pop(name, None)
    os.chdir(ROOT)
    print("Starting Dex. Leave this window open while using the app.", flush=True)
    os.execv(str(PYTHON), [str(PYTHON), "-I", "-m", "pokemon_hunter.beta.cli", "--root", str(ROOT), "serve"])


if __name__ == "__main__":
    main()
