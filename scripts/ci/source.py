"""Check shipped JavaScript and local links in the maintained reader documentation."""

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
DOCS = (
    "README.md",
    "docs/CI.md",
    "docs/SSOT.md",
    "docs/local-development.md",
    "docs/operations.md",
    "docs/SECURITY.md",
    "docs/UI_DESIGN.md",
    "docs/catalogs.md",
    "docs/hunts.md",
    "docs/photo-entry.md",
    "docs/ERROR_HANDLING.md",
    "docs/ORIGINAL_APP.md",
    "docs/legacy-watcher.md",
    "config/catalog-imports/staging-ten/README.md",
)


def check():
    scripts = sorted((ROOT / "src/pokemon_hunter/beta/static").glob("*.js")) + sorted(
        (ROOT / "web").glob("*.js")
    )
    if not scripts:
        raise ValueError("No supported JavaScript collected")
    for script in scripts:
        subprocess.run(["node", "--check", str(script)], check=True, timeout=30)
    broken = []
    for relative in DOCS:
        document = ROOT / relative
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
            target = target.strip("<>").split(' "', 1)[0]
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            if parsed.path.startswith("/"):
                broken.append(f"{relative}: nonportable absolute path {target}")
                continue
            if not (document.parent / unquote(parsed.path)).exists():
                broken.append(f"{relative}: {target}")
    if broken:
        raise ValueError("Broken local documentation references:\n" + "\n".join(broken))
    print(f"Checked {len(scripts)} JavaScript files and {len(DOCS)} maintained documents")


if __name__ == "__main__":
    check()
