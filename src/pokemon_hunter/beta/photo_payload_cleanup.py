"""Remove only registered temporary payloads left by older installed providers.

Legacy lock names are storage compatibility, not executable recognition support.
"""

import fcntl
import hashlib
import json
import os
import shutil
import time
from pathlib import Path


def payload_home(root, create=False):
    root = Path(root).resolve()
    parent = root.parent / ".dex-photo-batches" / hashlib.sha256(str(root).encode()).hexdigest()
    path = parent / "payloads"
    if create:
        parent.parent.mkdir(mode=0o700, exist_ok=True)
        parent.mkdir(mode=0o700, exist_ok=True)
        path.mkdir(mode=0o700, exist_ok=True)
    return path


def cleanup_payloads(root):
    """Only registered owned directories, after any live adapter releases its lock."""
    home = payload_home(root)
    registry = home / "owned.jsonl"
    if not registry.exists():
        return
    lock = os.open(Path(root) / "codex-recognition.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        for line in registry.read_text().splitlines():
            record = json.loads(line)
            name = record["name"]
            if not isinstance(name, str) or not name.startswith("dex-batch-") or Path(name).name != name:
                raise ValueError("Invalid owned photo payload registry")
            path = home / name
            if path.is_dir() and not path.is_symlink() and record["created"] < time.time() - 90:
                shutil.rmtree(path)
    finally:
        os.close(lock)
