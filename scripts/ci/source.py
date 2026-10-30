"""Check shipped JavaScript syntax and portable documentation references."""

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
    "docs/price-snapshots.md",
    "docs/operations.md",
    "docs/SECURITY.md",
    "docs/UI_DESIGN.md",
    "docs/catalogs.md",
    "docs/hunts.md",
    "docs/photo-entry.md",
    "docs/artwork.md",
    "docs/card-groups.md",
    "docs/account-reads.md",
    "docs/frontend-reads.md",
    "docs/effective-collection.md",
    "docs/ERROR_HANDLING.md",
    "docs/ORIGINAL_APP.md",
    "docs/legacy-watcher.md",
    "config/catalog-imports/staging-ten/README.md",
)


def heading_anchors(document):
    """GitHub-style anchors for ATX headings in the maintained Markdown guides."""
    anchors = set()
    fence = None
    for line in document.read_text().splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        anchors.update(re.findall(r'<a\s+(?:id|name)=["\x27]([^"\x27]+)["\x27]', line, flags=re.IGNORECASE))
        heading = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not heading:
            continue
        label = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading[1])
        label = re.sub(r"<[^>]*>", "", label)
        slug = re.sub(r"[^\w\- ]", "", label.lower()).replace(" ", "-")
        anchor = slug
        suffix = 0
        while anchor in anchors:
            suffix += 1
            anchor = f"{slug}-{suffix}"
        anchors.add(anchor)
    return anchors


def check_document_links():
    """Reports are generated, ignored evidence, never prerequisites for a checkout."""
    broken = []
    for relative in DOCS:
        document = ROOT / relative
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
            target = target.strip("<>").split(' "', 1)[0]
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            if parsed.path.startswith("/"):
                broken.append(f"{relative}: nonportable absolute path {target}")
                continue
            destination = (document.parent / unquote(parsed.path)).resolve() if parsed.path else document
            if destination.is_relative_to((ROOT / "reports").resolve()):
                broken.append(f"{relative}: generated evidence is not a portable link {target}")
            elif not destination.exists():
                broken.append(f"{relative}: {target}")
            elif parsed.fragment and destination.suffix.lower() == ".md":
                if unquote(parsed.fragment) not in heading_anchors(destination):
                    broken.append(f"{relative}: missing section {target}")
    if broken:
        raise ValueError("Broken local documentation references:\n" + "\n".join(broken))


def check():
    scripts = (
        sorted((ROOT / "src/pokemon_hunter/beta/static").glob("*.js"))
        + sorted((ROOT / "web").glob("*.js"))
        + sorted((ROOT / "scripts").glob("*.js"))
        + sorted((ROOT / "scripts").glob("*.cjs"))
    )
    if not scripts:
        raise ValueError("No supported JavaScript collected")
    for script in scripts:
        subprocess.run(["node", "--check", str(script)], check=True, timeout=30)
    check_document_links()
    print(f"Checked {len(scripts)} JavaScript files and {len(DOCS)} maintained documents")


if __name__ == "__main__":
    check()
