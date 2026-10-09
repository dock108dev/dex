"""Retained-only batch orchestration over existing catalogs and journals.

No provider I/O. Checkpoints contain immutable reviewed packages and child journal IDs;
publication never writes ownership, goals, photos or research.
"""

import copy
import json
import uuid
from collections import Counter, defaultdict
from typing import Literal

from django.db import connection
from django.http import Http404
from pydantic import BaseModel, ConfigDict, Field

from pokemon_hunter.migration import encode

from . import canonical_species, store, transactions
from . import catalog_imports as cat
from . import collection as inv
from . import sealed_catalog as sealed
from .catalog_coverage import ROOT as ROOT
from .catalog_coverage import coverage as coverage
from .catalog_coverage import coverage_profile as coverage_profile
from .catalog_coverage import indexed_eras as indexed_eras
from .catalog_coverage import retained_batch as retained_batch
from .catalog_coverage import verify_retained_inputs as verify_retained_inputs


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    set_id: str
    language: str
    era: str
    medium: Literal["physical", "digital", "unknown"]
    release_status: Literal["released", "unreleased", "uncertain"]
    source_url: str
    source_time: str | None
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_class: Literal["retained-real-source", "synthetic"]
    enumerated_ids: list[str] | None
    enumeration_complete: bool
    expected_target_count: int | None = Field(default=None, ge=0)
    source_status: Literal["usable", "unavailable"] = "usable"
    package: dict
    numbered_mappings: dict[str, str] = Field(default_factory=dict)


class Batch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["dex-target-batch-v1"]
    version: str = Field(min_length=1, max_length=120)
    mode: Literal["atomic", "checkpoint"]
    sets: list[Assessment] = Field(min_length=1, max_length=250)


def initialize():
    with connection.cursor() as cursor:
        cursor.execute("""CREATE TABLE IF NOT EXISTS catalog_batches(
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            package TEXT NOT NULL, package_hash TEXT UNIQUE NOT NULL,
            state TEXT NOT NULL, baseline TEXT NOT NULL, outcomes TEXT NOT NULL,
            created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")


def state_hash():
    return cat.fingerprint(
        {
            "sealed": sealed.publication_hash(),
            "catalogs": store.rows(
                "SELECT * FROM catalog_sets WHERE publication_state='published' ORDER BY id"
            ),
            "printings": store.rows(
                "SELECT * FROM printings WHERE publication_state='published' ORDER BY id"
            ),
            "heads": store.rows("SELECT * FROM catalog_heads ORDER BY set_id"),
        }
    )


def assess(raw):
    """Explicit mappings establish eligibility; names and legacy eligibility never do."""
    a = Assessment.model_validate(raw).model_dump()
    p = a["package"]
    if a["source_status"] == "unavailable":
        return dict(
            set_id=a["set_id"],
            language=a["language"],
            era=a["era"],
            medium=a["medium"],
            release_status=a["release_status"],
            source_url=a["source_url"],
            source_time=a["source_time"],
            source_sha256=a["source_sha256"],
            evidence_class=a["evidence_class"],
            status="source-unavailable",
            expected_target_count=None,
            target_numbered_count=0,
            supplied_variant_records=0,
            variant_completeness="unknown",
            distribution_completeness="unknown",
            distribution={},
            exceptions=[dict(reason="source-unavailable")],
            excluded_above251=[],
            species=[],
            target_records=[],
            enumeration_complete=False,
            fatal=False,
        )
    if p.get("schema_version") == "dex-sealed-v1":
        expansions = [e for e in p["expansions"] if e["id"] == a["set_id"]]
        if len(expansions) != 1 or expansions[0]["language"] != a["language"]:
            raise ValueError("Assessment expansion/language conflict")
        if not any(s["sha256"] == a["source_sha256"] and s["url"] == a["source_url"] for s in p["sources"]):
            raise ValueError("Assessment source identity missing")
        cards = []
        mappings = [m for m in p["mappings"] if m["kind"] == "printings"]
        for r in p["printings"]:
            if r["expansion_id"] != a["set_id"]:
                continue
            external = [m["external_id"] for m in mappings if m["internal_id"] == r["id"]]
            cards.append(
                dict(
                    external_id=r["id"],
                    numbered_id=external[0] if external else r["id"],
                    number=r["number"],
                    name=r["name"],
                    rarity=r["rarity"],
                    pokemon_dex=int(r["species_id"].split(":")[1]) if r["species_id"] else None,
                    category=r["category"],
                    variant=r["variant"],
                    finish=r["finish"],
                )
            )
        memberships = {m["printing_id"]: m["status"] for m in p["memberships"]}
    elif p.get("schema_version") == "dex-catalog-v1":
        if a["set_id"] != f"{p['provider']}:{p['language']}:{p['set_key']}" or a["language"] != p["language"]:
            raise ValueError("Assessment and package identity conflict")
        if p["source_sha256"] != a["source_sha256"]:
            raise ValueError("Assessment source hash conflict")
        cards = [
            dict(
                c,
                numbered_id=c["external_id"],
                pokemon_dex=c.get("metadata", {}).get("pokemon_dex"),
                rarity=c.get("metadata", {}).get("rarity"),
                category={"Pokémon": "pokemon", "Trainer": "trainer", "Energy": "energy"}.get(
                    c.get("metadata", {}).get("supertype"), "unknown"
                ),
            )
            for c in p["cards"]
        ]
        memberships = {}
    else:
        raise ValueError("Unsupported retained package")
    if a["source_time"] is not None:
        sealed.instant(a["source_time"])
    for c in cards:
        c["numbered_id"] = a["numbered_mappings"].get(c["external_id"], c["numbered_id"])
    unique, exceptions, excluded = {}, [], []
    fatal = False
    for c in cards:
        identity = c["external_id"]
        if identity in unique:
            if unique[identity] == c:
                exceptions.append(dict(identity=identity, reason="duplicate-provider-record-coalesced"))
                continue
            exceptions.append(dict(identity=identity, reason="conflicting-provider-identity"))
            fatal = True
            continue
        unique[identity] = c
    target = []
    numbered_species = defaultdict(set)
    for c in unique.values():
        numbered_species[c["numbered_id"]].add(c["pokemon_dex"])
    for identity, numbers in numbered_species.items():
        if len(numbers) > 1:
            fatal = True
            exceptions.append(dict(identity=identity, reason="conflicting-numbered-species-mapping"))
    for c in unique.values():
        n = c["pokemon_dex"]
        if c["category"] in {"trainer", "energy"} and n is None:
            continue
        if c["category"] != "pokemon" or n is None:
            exceptions.append(dict(identity=c["external_id"], reason="unresolved-canonical-mapping"))
            continue
        try:
            canonical_species.require(n)
        except ValueError:
            exceptions.append(dict(identity=c["external_id"], reason="invalid-canonical-mapping"))
            continue
        if n > 251:
            excluded.append(c["external_id"])
            continue
        target.append(c)
    enumerated = a["enumerated_ids"]
    numbered = {c["numbered_id"] for c in unique.values()}
    source_count = (
        expansions[0]["expected_printings"]
        if p["schema_version"] == "dex-sealed-v1"
        else p["expected_count"]
        if p.get("coverage") == "catalog-entries"
        else None
    )
    full = (
        a["enumeration_complete"]
        and enumerated is not None
        and set(enumerated) == numbered
        and source_count == len(numbered)
    )
    if enumerated is not None and len(enumerated) != len(set(enumerated)):
        fatal = True
        exceptions.append(dict(reason="duplicate-enumeration-identity"))
    if a["enumeration_complete"] and not full:
        exceptions.append(dict(reason="truncated-enumeration"))
    mapping_gaps = any("mapping" in e["reason"] for e in exceptions)
    scope = a["language"] == "en" and a["medium"] == "physical" and a["release_status"] == "released"
    complete = full and not mapping_gaps and not fatal and scope
    count = len({c["numbered_id"] for c in target})
    if a["expected_target_count"] is not None and a["expected_target_count"] != count:
        exceptions.append(dict(reason="target-count-conflict"))
        fatal = True
        complete = False
    status = (
        "conflict"
        if fatal
        else "out-of-scope"
        if not scope
        else "confirmed-zero-target"
        if complete and count == 0
        else "completely-enumerated-targets"
        if complete
        else "partially-assessed"
    )
    distribution = Counter(memberships.get(c["external_id"], "unknown") for c in target)
    for c in target:
        if memberships.get(c["external_id"], "unknown") == "unknown":
            exceptions.append(dict(identity=c["external_id"], reason="distribution-unknown"))
        if c.get("variant") is None or c.get("finish") is None:
            exceptions.append(dict(identity=c["external_id"], reason="physical-variant-unknown"))
    return dict(
        set_id=a["set_id"],
        language=a["language"],
        era=a["era"],
        medium=a["medium"],
        release_status=a["release_status"],
        source_url=a["source_url"],
        source_time=a["source_time"],
        source_sha256=a["source_sha256"],
        evidence_class=a["evidence_class"],
        status=status,
        expected_target_count=count if complete else a["expected_target_count"],
        target_numbered_count=count if scope else 0,
        out_of_scope_numbered_count=count if not scope else 0,
        supplied_variant_records=len(target) if scope else 0,
        variant_completeness="unknown",
        distribution_completeness="unknown",
        distribution=dict(distribution) if scope else {},
        exceptions=exceptions,
        excluded_above251=excluded,
        species=sorted({c["pokemon_dex"] for c in target}) if scope else [],
        target_records=target if scope else [],
        enumeration_complete=complete,
        fatal=fatal,
    )


def prepared(a, report):
    """Legacy exact reconciliation stays intact; new packages import resolved targets only."""
    p = copy.deepcopy(a["package"])
    if report["status"] in {"out-of-scope", "source-unavailable"}:
        return None
    if p["schema_version"] == "dex-sealed-v1":
        # Existing sealed schema preserves non-target source metadata and exact bridges.
        return p
    if p.get("reconcile_legacy_set"):
        return p
    ids = {c["external_id"] for c in report["target_records"]}
    seen = set()
    p["cards"] = [
        c
        for c in p["cards"]
        if c["external_id"] in ids and not (c["external_id"] in seen or seen.add(c["external_id"]))
    ]
    if not p["cards"]:
        return None
    p["coverage"] = "partial"
    p["expected_count"] = max(p["expected_count"], len(p["cards"]))
    for c in p["cards"]:
        c["metadata"]["dex_eligible"] = True
    return p


def publish_one(actor, a, report):
    p = prepared(a, report)
    if p is None:
        return dict(state="assessed-only", child=None, created=False)
    service = sealed if p["schema_version"] == "dex-sealed-v1" else cat
    op = service.preview(actor, p)
    if service is cat and op["preview"]["archived"]:
        raise inv.Conflict("Target batch cannot implicitly archive catalog identities")
    prior_state = op["state"]
    if prior_state == "preview":
        service.transition(actor, op["id"], "verify")
    if prior_state in {"preview", "verified"}:
        service.transition(actor, op["id"], "publish")
    elif prior_state != "published":
        raise inv.Conflict("Rolled-back child needs a fresh reviewed source version")
    return dict(
        state="published",
        child=op["id"],
        kind="sealed" if service is sealed else "catalog",
        created=prior_state != "published",
        impact=sealed.review(op) if service is sealed else op["preview"],
    )


def get(actor, key):
    cat.admin(actor)
    rows = store.rows("SELECT * FROM catalog_batches WHERE id=%s", [key])
    if not rows:
        raise Http404
    row = rows[0]
    for field in ("package", "outcomes"):
        row[field] = json.loads(row[field])
    row["completed_sets"] = sum("publication" in r for r in row["outcomes"])
    return row


@transactions.atomic
def preview(actor, raw):
    cat.admin(actor)
    initialize()
    sealed.initialize()
    p = Batch.model_validate(raw).model_dump()
    ids = [a["set_id"] for a in p["sets"]]
    if len(ids) != len(set(ids)):
        raise ValueError("One assessment per set per batch")
    reports = [assess(a) for a in p["sets"]]
    if any(r["fatal"] for r in reports):
        return dict(state="invalid", outcomes=reports, published=0)
    hashed = cat.fingerprint(p)
    found = store.rows("SELECT id FROM catalog_batches WHERE package_hash=%s", [hashed])
    if found:
        return get(actor, found[0]["id"])
    if any(
        json.loads(r["package"])["version"] == p["version"]
        for r in store.rows("SELECT package FROM catalog_batches")
    ):
        raise ValueError("Changed source requires a new batch version")
    # Exercise actual services sequentially under a rollback-only savepoint. This catches
    # cross-set aliases, mappings, references and stale journals before any durable child.
    try:
        with transactions.atomic():
            for a, r in zip(p["sets"], reports, strict=True):
                result = publish_one(actor, a, r)
                r["impact"] = result.get("impact", {})
            from django.db import transaction

            transaction.set_rollback(True)
    except (ValueError, inv.Conflict):
        r["fatal"] = True
        r["status"] = "conflict"
        r["exceptions"].append(dict(reason="existing-journal-validation-conflict"))
        return dict(state="invalid", outcomes=reports, published=0)
    key = str(uuid.uuid4())
    inv.execute(
        "INSERT INTO catalog_batches(id,user_id,package,package_hash,state,baseline,outcomes) "
        "VALUES(%s,%s,%s,%s,'preview',%s,%s)",
        [key, actor.user_id, encode(p), hashed, state_hash(), encode(reports)],
    )
    cat.audit(actor, "batch-preview", key, dict(hash=hashed, sets=len(ids)))
    return get(actor, key)


@transactions.atomic
def transition(actor, key, action, limit=1, expected_completed=None):
    op = get(actor, key)
    if type(limit) is not int or not 1 <= limit <= 250:
        raise ValueError("Bound local execution to 1..250 sets")
    if (action, op["state"]) in {
        ("verify", "verified"),
        ("publish", "published"),
        ("rollback", "rolled-back"),
    }:
        return op
    if action == "publish" and expected_completed is not None:
        if type(expected_completed) is not int or expected_completed < 0:
            raise ValueError("Invalid checkpoint confirmation")
        if expected_completed < op["completed_sets"]:
            return op  # Re-delivered confirmation never advances another checkpoint.
        if expected_completed != op["completed_sets"]:
            raise inv.Conflict("Checkpoint confirmation is ahead of local state")
    if op["baseline"] != state_hash():
        raise inv.Conflict("Catalog changed since review/checkpoint; preview a successor batch")
    if action == "verify":
        if op["state"] != "preview":
            raise ValueError("Review a preview first")
        state = "verified"
    elif action == "publish":
        if op["state"] not in {"verified", "partial"}:
            raise ValueError("Verify before publication")
        pending = [i for i, r in enumerate(op["outcomes"]) if "publication" not in r]
        selected = pending if op["package"]["mode"] == "atomic" else pending[:limit]
        for i in selected:
            r = op["outcomes"][i]
            r["publication"] = publish_one(actor, op["package"]["sets"][i], r)
        state = "published" if len(selected) == len(pending) else "partial"
    elif action == "rollback":
        if op["state"] not in {"partial", "published"}:
            raise ValueError("Rollback a published batch/checkpoint")
        for r in reversed(op["outcomes"]):
            pub = r.get("publication", {})
            if pub.get("created"):
                service = sealed if pub["kind"] == "sealed" else cat
                service.transition(actor, pub["child"], "rollback")
                pub["state"] = "rolled-back"
        state = "rolled-back"
    else:
        raise ValueError("Unknown batch action")
    inv.execute(
        "UPDATE catalog_batches SET state=%s,baseline=%s,outcomes=%s WHERE id=%s",
        [state, state_hash(), encode(op["outcomes"]), key],
    )
    cat.audit(actor, "batch-" + action, key, dict(state=state, limit=limit))
    return get(actor, key)
