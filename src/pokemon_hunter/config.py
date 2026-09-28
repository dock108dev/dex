import os
from pathlib import Path

import yaml

from .models import Settings


def load_env(path: Path) -> None:
    """Read simple KEY=value data; never execute a shell or overwrite existing env."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not key.strip().replace("_", "").isalnum():
            raise ValueError("Invalid .env entry; use KEY=value")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def load_config(root: Path):
    data = yaml.safe_load((root / "config/settings.yaml").read_text())
    if os.getenv("EBAY_DELIVERY_POSTAL_CODE"):
        data["delivery_postal_code"] = os.environ["EBAY_DELIVERY_POSTAL_CODE"]
    settings = Settings.model_validate(data)
    sets = yaml.safe_load((root / "config/sets.yaml").read_text())
    queries = yaml.safe_load((root / "config/searches.yaml").read_text())["queries"]
    if not isinstance(queries, list) or not queries or any(not isinstance(q, str) for q in queries):
        raise ValueError("Searches must be a nonempty list of strings")
    return settings, sets, list(dict.fromkeys(queries))
