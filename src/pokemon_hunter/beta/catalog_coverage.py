"""Read-only projections of pinned coverage profiles and publication journals."""

import hashlib
import json
from collections import Counter, defaultdict

from django.db import connection

from pokemon_hunter.runtime_data import root

from . import collection as inv
from . import sealed_catalog as sealed
from . import store

ROOT = root()


def verify_retained_inputs():
    lock = json.loads((ROOT / "config/catalog-pipeline/inputs.json").read_text())
    for name, expected in lock["files"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Pinned retained input changed; explicit source review required: " + name)


def retained_batch():
    verify_retained_inputs()
    return json.loads((ROOT / "config/catalog-pipeline/retained-20261004.json").read_text())


def coverage_profile(profile="current"):
    """Reviewed read-only identity migration; historical projection is its reversal.

    No catalog rows, journal baselines or frozen references are rewritten.
    """
    if profile == "historical":
        return json.loads((ROOT / "config/catalog-pipeline/universe-20261004.json").read_text()), {}
    if profile != "current":
        raise ValueError("Unknown coverage profile")
    config = json.loads((ROOT / "config/catalog-pipeline/m4-20261006/coverage-profile.json").read_text())
    for name in ("universe", "review"):
        if hashlib.sha256((ROOT / config[name]).read_bytes()).hexdigest() != config[name + "_sha256"]:
            raise ValueError("Reviewed coverage input changed: " + name)
    manifest = json.loads((ROOT / config["universe"]).read_text())
    review = json.loads((ROOT / config["review"]).read_text())
    if config["identities"] != review["identities"]:
        raise ValueError("Coverage identities differ from reviewed mappings")
    aliases = {r["current_assessment_id"]: r["expansion_id"] for r in config["identities"]}
    ids = {r["id"] for r in manifest["sets"]}
    if len(ids) != len(manifest["sets"]) or any(v not in ids for v in aliases.values()):
        raise ValueError("Duplicate or missing reviewed universe identity")
    return manifest, aliases


def coverage(actor, profile="current"):
    store.verified(actor)
    manifest, aliases = coverage_profile(profile)
    rows = {
        r["id"]: dict(
            r,
            set_id=r["id"],
            source_target_numbered_count=r.get("target_numbered_count"),
            source_supplied_variant_records=r.get("supplied_variant_records"),
            source_enumeration_complete=r.get("enumeration_complete"),
            status="unassessed",
            enumeration_complete=False,
            variant_completeness="unknown",
            distribution_completeness="unknown",
            expected_target_count=None,
            target_numbered_count=0,
            supplied_variant_records=0,
            species=[],
            exceptions=[],
            reviewed_records=0,
            published_records=0,
            distribution={},
        )
        for r in manifest["sets"]
    }
    active_members = (
        {m["printing_id"]: m["status"] for m in sealed.records()["memberships"].values()}
        if "sealed_memberships" in connection.introspection.table_names()
        else {}
    )
    catalog_members = {}
    if "sealed_bridges" in connection.introspection.table_names():
        for m in store.rows(
            "SELECT m.provider,m.external_id,b.printing_id FROM external_mappings m "
            "JOIN sealed_bridges b ON b.catalog_id=m.internal_id WHERE m.entity_kind='printing'"
        ):
            catalog_members[m["provider"], m["external_id"]] = active_members.get(m["printing_id"], "unknown")

    def memberships_for(a, published):
        p = a["package"]
        if published and p["schema_version"] == "dex-sealed-v1":
            return active_members
        if published and p["schema_version"] == "dex-catalog-v1":
            provider = p["provider"] + ":" + p["language"]
            return {
                c["external_id"]: catalog_members.get((provider, c["external_id"]), "unknown")
                for c in p["cards"]
            }
        return {m["printing_id"]: m["status"] for m in p.get("memberships", [])}

    synthetic, latest = [], {}
    batches = (
        store.rows("SELECT id,state,outcomes,package FROM catalog_batches ORDER BY created,id")
        if "catalog_batches" in connection.introspection.table_names()
        else []
    )
    for b in batches:
        if b["state"] not in {"verified", "partial", "published"}:
            continue
        assessments = {a["set_id"]: a for a in json.loads(b["package"])["sets"]}
        for r in json.loads(b["outcomes"]):
            if r["evidence_class"] == "synthetic":
                synthetic.append({k: v for k, v in r.items() if k not in {"target_records", "impact"}})
                continue
            pub = r.get("publication", {})
            published = pub.get("state") == "published"
            if pub.get("child"):
                table = "sealed_imports" if pub["kind"] == "sealed" else "catalog_imports"
                child = store.rows(f"SELECT state FROM {table} WHERE id=%s", [pub["child"]])
                published = published and bool(child) and child[0]["state"] == "published"
            if published:
                members = memberships_for(assessments[r["set_id"]], published)
                r = dict(
                    r,
                    distribution=dict(
                        Counter(members.get(c["external_id"], "unknown") for c in r["target_records"])
                    ),
                )
                r["exceptions"] = [
                    e
                    for e in r["exceptions"]
                    if e.get("reason") != "distribution-unknown"
                    or members.get(e.get("identity"), "unknown") == "unknown"
                ]
            rr = {k: v for k, v in r.items() if k not in {"target_records", "publication", "impact"}}
            rr.update(
                reviewed_records=r["supplied_variant_records"],
                published_records=r["supplied_variant_records"] if published else 0,
            )
            canonical = aliases.get(r["set_id"], r["set_id"])
            if profile == "current" and canonical not in rows:
                raise inv.Conflict("Assessment outside reviewed source universe: " + r["set_id"])
            rr.update(set_id=canonical, assessment_id=r["set_id"])
            rows[canonical] = dict(rows.get(canonical, dict(name=canonical, id=canonical)), **rr)
            latest[canonical] = (r, assessments[r["set_id"]], published)
    species = {
        n: dict(
            dex=n,
            sets=[],
            target_numbered_count=0,
            supplied_variant_records=0,
            expected_all_era_count=None,
            distribution={},
            exceptions=[],
            reviewed_records=0,
            published_records=0,
        )
        for n in range(1, 252)
    }
    for set_id, (r, a, published) in latest.items():
        members = memberships_for(a, published)
        for n in r["species"]:
            entry = species[n]
            cards = [c for c in r["target_records"] if c["pokemon_dex"] == n]
            entry["sets"].append(set_id)
            entry["target_numbered_count"] += len({c["numbered_id"] for c in cards})
            entry["supplied_variant_records"] += len(cards)
            entry["reviewed_records"] += len(cards)
            entry["published_records"] += len(cards) if published else 0
            identities = {c["external_id"] for c in cards}
            entry["exceptions"].extend(e for e in r["exceptions"] if e.get("identity") in identities)
            entry["distribution"] = dict(
                Counter(entry["distribution"])
                + Counter(members.get(c["external_id"], "unknown") for c in cards)
            )
    eras = defaultdict(list)
    for r in rows.values():
        eras[r["era"]].append(r)
    values = list(rows.values())
    return dict(
        universe_date=manifest["source_time"],
        universe_version=manifest["version"],
        current_universe=profile == "current",
        coverage_profile=profile,
        universe_source_url=manifest.get("source_url"),
        universe_source_sha256=manifest.get("source_sha256"),
        reviewed_identity_mappings=aliases,
        source_totals=dict(
            sets=len(manifest["sets"]),
            physical=sum(r["medium"] == "physical" for r in manifest["sets"]),
            digital=sum(r["medium"] == "digital" for r in manifest["sets"]),
            target_numbered_count=sum(
                r.get("target_numbered_count", 0) for r in manifest["sets"] if r["medium"] == "physical"
            ),
            completely_enumerated_physical=sum(
                r.get("enumeration_complete", False) for r in manifest["sets"] if r["medium"] == "physical"
            ),
        ),
        sets=values,
        species=list(species.values()),
        synthetic=synthetic,
        eras=[
            dict(
                era=k,
                sets=len(v),
                assessed=sum(r["status"] != "unassessed" for r in v),
                target_numbered_count=sum(r["target_numbered_count"] for r in v),
                supplied_variant_records=sum(r["supplied_variant_records"] for r in v),
                reviewed_records=sum(r["reviewed_records"] for r in v),
                published_records=sum(r["published_records"] for r in v),
                expected_target_count=None,
                distribution=dict(sum((Counter(r["distribution"]) for r in v), Counter())),
                exceptions=sum(len(r["exceptions"]) for r in v),
            )
            for k, v in eras.items()
        ],
        totals=dict(
            sets=len(values),
            assessed=sum(r["status"] != "unassessed" for r in values),
            unassessed=sum(r["status"] == "unassessed" for r in values),
            target_numbered_count=sum(r["target_numbered_count"] for r in values),
            supplied_variant_records=sum(r["supplied_variant_records"] for r in values),
            published_records=sum(r["published_records"] for r in values),
        ),
        explanation=(
            "Current application coverage uses the reviewed pinned D6 universe as of its original source time. "
            if profile == "current"
            else "Historical October 4 universe. "
        )
        + "Unassessed application sets are gaps, not zero-target sets. Source enumeration is separate from publication. "
        "Indexed printings do not establish booster contents; variant and distribution completeness remain separate.",
    )


def indexed_eras():
    """Read-only provider series pivot; never invent a release year or rewrite printings."""
    manifest, aliases = coverage_profile()
    external = {
        (r["provider"] + ":" + r["language"], r["provider_set_id"]): r["era"] for r in manifest["sets"]
    }
    for assessment_id, canonical in aliases.items():
        row = next(r for r in manifest["sets"] if r["id"] == canonical)
        provider, language, key = assessment_id.split(":", 2)
        external[provider + ":" + language, key] = row["era"]
    if "catalog_batches" in connection.introspection.table_names():
        for b in store.rows(
            "SELECT package,outcomes FROM catalog_batches WHERE state IN ('partial','published') ORDER BY created,id"
        ):
            outcomes = {r["set_id"]: r for r in json.loads(b["outcomes"])}
            for a in json.loads(b["package"])["sets"]:
                pub = outcomes[a["set_id"]].get("publication", {})
                if pub.get("state") != "published":
                    continue
                p = a["package"]
                if p.get("schema_version") == "dex-catalog-v1":
                    external[p["provider"] + ":" + p["language"], p["set_key"]] = a["era"]
    return {
        m["internal_id"]: external[m["provider"], m["external_id"]]
        for m in store.rows("SELECT * FROM external_mappings WHERE entity_kind='set'")
        if (m["provider"], m["external_id"]) in external
    }
