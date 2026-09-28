"""Explicit, pinned reconciliation of the original ten sets. Never fuzzy matching."""

import json
import re
from pathlib import Path

from pokemon_hunter.inventory import stable_id

from . import store

PACKAGES = Path(__file__).resolve().parents[3] / "config/catalog-imports/staging-ten"


def approved(package):
    key = package.get("reconcile_legacy_set")
    if not key or not re.fullmatch(r"[a-z_0-9]+", key):
        raise ValueError("Invalid explicit legacy set mapping")
    path = PACKAGES / (key + ".json")
    if not path.is_file():
        raise ValueError("Unreviewed legacy mapping")
    # Reconciliation is only enabled for the exact reviewed source package shipped here.
    from .catalog_imports import Package

    if (
        Package.model_validate(json.loads(path.read_text())).model_dump()
        != Package.model_validate(package).model_dump()
    ):
        raise ValueError("Reconciliation requires the pinned reviewed package")


def set_id(package):
    key = package["reconcile_legacy_set"]
    found = store.rows(
        "SELECT internal_id FROM external_mappings WHERE provider='legacy' AND entity_kind='set' AND external_id=%s",
        [key],
    )
    return found[0]["internal_id"] if found else stable_id("set", "pokemon:" + key)


def printing(package, card, sid):
    found = store.rows(
        "SELECT internal_id FROM external_mappings WHERE provider='legacy' AND entity_kind='printing' AND external_id IN (%s,%s)",
        [card["legacy_id"] + ":unresolved", card["legacy_id"] + ":first_edition"],
    )
    candidates = store.rows(
        "SELECT * FROM printings WHERE set_id=%s AND collector_number=%s", [sid, card["number"]]
    )
    ids = {r["internal_id"] for r in found} | {r["id"] for r in candidates}
    if len(ids) > 1:
        raise ValueError("Ambiguous printing variants; explicit additional review required")
    if ids:
        pid = next(iter(ids))
        old = store.rows("SELECT * FROM printings WHERE id=%s", [pid])
        if (
            not old
            or old[0]["set_id"] != sid
            or old[0]["collector_number"] != card["number"]
            or json.loads(old[0]["provenance"]).get("legacy_id") != card["legacy_id"]
        ):
            raise ValueError("Legacy identity evidence does not match the reviewed mapping")
        return pid, old[0]
    return stable_id("printing", "pokemon:legacy:" + card["legacy_id"] + ":unresolved"), None


def request_set_id(key):
    game, language, external = key.split(":")
    if game == "pokemon":
        found = store.rows(
            "SELECT internal_id FROM external_mappings WHERE provider=%s AND entity_kind='set' AND external_id=%s",
            ["tcgdex:" + language, external],
        )
        if found:
            return found[0]["internal_id"]
    return stable_id("catalog-set", key)


def publish_all(actor):
    """Operator-only, existing journaled importer; repeated invocation is idempotent."""
    from . import catalog_imports as cat

    for path in sorted(PACKAGES.glob("*.json")):
        if path.name in {"source-manifest.json", "species.json"}:
            continue
        op = cat.preview(actor, json.loads(path.read_text()))
        if op["state"] == "preview":
            cat.transition(actor, op["id"], "verify")
        cat.transition(actor, op["id"], "publish")
