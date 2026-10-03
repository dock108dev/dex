import os
from pathlib import Path

import yaml

from .models import Settings


def read_env(path: Path, *, keys=None):
    """Parse simple values without execution or environment mutation; first value wins.

    An explicit allowlist isolates a provider from unrelated local credentials.
    """
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip()
        if keys is not None and key not in keys:
            continue
        if not sep or not key.replace("_", "").isalnum():
            raise ValueError("Invalid .env entry; use KEY=value")
        values.setdefault(key, value.strip().strip("\"'"))
    return values


def load_env(path: Path) -> None:
    """Load parsed values without overwriting the process environment."""
    for key, value in read_env(path).items():
        os.environ.setdefault(key, value)


def load_settings(root: Path, *, environ=None, required=True):
    """Shared provider settings policy; beta may use defaults when its file is absent."""
    path = root / "config/settings.yaml"
    data = yaml.safe_load(path.read_text()) if required or path.is_file() else {}
    if not isinstance(data, dict):
        raise ValueError("Settings must be a mapping")
    environ = os.environ if environ is None else environ
    if environ.get("EBAY_DELIVERY_POSTAL_CODE"):
        data = {**data, "delivery_postal_code": environ["EBAY_DELIVERY_POSTAL_CODE"]}
    return Settings.model_validate(data)


def load_config(root: Path):
    settings = load_settings(root)
    sets = yaml.safe_load((root / "config/sets.yaml").read_text())
    queries = yaml.safe_load((root / "config/searches.yaml").read_text())["queries"]
    if not isinstance(queries, list) or not queries or any(not isinstance(q, str) for q in queries):
        raise ValueError("Searches must be a nonempty list of strings")
    return settings, sets, list(dict.fromkeys(queries))
