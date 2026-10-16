"""Disposable fake-CLI server; refuses ordinary roots and real recognition dispatch."""

import argparse
import shutil
import sys
import threading
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from serve_e4a import run  # noqa: E402


def main(args):
    root = args.root.resolve()
    if not (root / "SYNTHETIC_ONLY").is_file() or args.port == 8011:
        raise ValueError("Disposable engineering root and ephemeral port required")
    fake = args.fake.resolve()
    if fake.name != "fake-on02-codex" or not fake.is_relative_to(root.parent):
        raise ValueError("Explicit engineering executable required")
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from pokemon_hunter.beta import scan_worker

    stop = threading.Event()
    original_which = shutil.which

    def only_fake(name, *a, **kw):
        return str(fake) if name == "codex" else original_which(name, *a, **kw)

    with patch("shutil.which", only_fake):
        worker = threading.Thread(target=scan_worker.run, args=(stop,), daemon=True)
        worker.start()
        try:
            run(root, args.output, args.port)
        finally:
            stop.set()
            worker.join(timeout=4)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--fake", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--port", type=int, required=True)
    main(p.parse_args())
