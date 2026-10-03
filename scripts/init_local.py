"""Create empty local state without ever overwriting an existing collection."""

import os
from pathlib import Path


def _create_private(target, content):
    # Exclusive creation preserves existing state, including a file created concurrently.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(content)


def initialize(root):
    for name in ("pokedex_251.json", "settings.yaml"):
        target = root / "config" / name
        if target.exists():
            continue
        source = target.with_name(target.stem + ".example" + target.suffix)
        # Read before creating the destination: a missing example must not leave
        # an empty file that a later initialization would mistake for saved state.
        _create_private(target, source.read_bytes())

    values = root / "config/market_values.json"
    if not values.exists():
        _create_private(values, b"[]\n")


if __name__ == "__main__":
    initialize(Path(__file__).resolve().parents[1])
