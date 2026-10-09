"""Explicit, pinned reconciliation of the original ten sets. Never fuzzy matching."""

import json
import re

from pokemon_hunter.inventory import stable_id
from pokemon_hunter.runtime_data import root

from . import store

PACKAGES = root() / "config/catalog-imports/staging-ten"


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


def identity_rows(package, sid):
    """Fresh package-local legacy evidence, including mappings outside this set."""
    existing = {r["id"]: r for r in store.rows("SELECT * FROM printings WHERE set_id=%s", [sid])}
    numbers = {}
    for row in existing.values():
        numbers.setdefault(row["collector_number"], []).append(row)
    mappings = {}
    for offset in range(0, len(package["cards"]), 250):
        keys = [
            c["legacy_id"] + suffix
            for c in package["cards"][offset : offset + 250]
            for suffix in (":unresolved", ":first_edition")
        ]
        placeholders = ",".join(["%s"] * len(keys))
        for row in store.rows(
            "SELECT external_id,internal_id FROM external_mappings "
            "WHERE provider='legacy' AND entity_kind='printing' "
            f"AND external_id IN ({placeholders})",
            keys,
        ):
            mappings.setdefault(row["external_id"], []).append(row)
    mapped_ids = sorted({r["internal_id"] for rows in mappings.values() for r in rows})
    for offset in range(0, len(mapped_ids), 500):
        ids = mapped_ids[offset : offset + 500]
        placeholders = ",".join(["%s"] * len(ids))
        existing.update(
            (r["id"], r) for r in store.rows(f"SELECT * FROM printings WHERE id IN ({placeholders})", ids)
        )
    return mappings, existing, numbers


def printing(package, card, sid, evidence=None):
    if evidence is None:
        found = store.rows(
            "SELECT internal_id FROM external_mappings WHERE provider='legacy' AND entity_kind='printing' AND external_id IN (%s,%s)",
            [card["legacy_id"] + ":unresolved", card["legacy_id"] + ":first_edition"],
        )
        candidates = store.rows(
            "SELECT * FROM printings WHERE set_id=%s AND collector_number=%s", [sid, card["number"]]
        )
    else:
        mappings, existing, numbers = evidence
        found = [
            row
            for suffix in (":unresolved", ":first_edition")
            for row in mappings.get(card["legacy_id"] + suffix, [])
        ]
        candidates = numbers.get(card["number"], [])
    ids = {r["internal_id"] for r in found} | {r["id"] for r in candidates}
    if len(ids) > 1:
        raise ValueError("Ambiguous printing variants; explicit additional review required")
    if ids:
        pid = next(iter(ids))
        old = (
            store.rows("SELECT * FROM printings WHERE id=%s", [pid])
            if evidence is None
            else [existing[pid]]
            if pid in existing
            else []
        )
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
