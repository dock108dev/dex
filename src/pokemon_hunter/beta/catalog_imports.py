"""Versioned, atomic catalog publication. Inventory identities are never deleted."""

import json
import re
import uuid
from typing import Literal

from django.core.exceptions import PermissionDenied
from django.http import Http404
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import digest, encode

from . import canonical_species, store
from . import collection as inv
from . import transactions as transaction

ADAPTERS = {
    "pokemon": {"name": "Pokémon", "version": "pokemon-catalog-v1", "synthetic": False},
    "synthetic-orbits": {"name": "Synthetic Orbits (test game)", "version": "orbits-v1", "synthetic": True},
}


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pokemon_dex: int | None = Field(default=None)
    dex_eligible: bool
    supertype: Literal["Pokémon", "Trainer", "Energy"]
    rarity: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def canonical_identity(self):
        if self.pokemon_dex is not None:
            canonical_species.require(self.pokemon_dex)
            if self.supertype != "Pokémon":
                raise ValueError("Non-Pokémon category cannot map to a canonical species")
        if self.dex_eligible and (self.supertype != "Pokémon" or self.pokemon_dex is None):
            raise ValueError("Eligibility requires resolved canonical Pokémon identity")
        return self


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    external_id: str = Field(min_length=1, max_length=120)
    number: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    legacy_id: str | None = None
    metadata: Metadata | None = None
    edition: str | None = None
    finish: str | None = None
    variant: str | None = None


class Package(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["dex-catalog-v1"]
    game: Literal["pokemon", "synthetic-orbits"]
    set_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    set_name: str = Field(min_length=1, max_length=120)
    language: str = Field(min_length=2, max_length=20)
    aliases: list[str] = Field(max_length=20)
    provider: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    version: str = Field(min_length=1, max_length=120)
    source_url: str = Field(min_length=1, max_length=500)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    metadata_permission: str = Field(min_length=1, max_length=1000)
    image_permission: Literal["not-included"]
    coverage: Literal["catalog-entries", "partial"]
    expected_count: int = Field(ge=1, le=2000)
    reconcile_legacy_set: str | None = None
    cards: list[Record] = Field(min_length=1, max_length=2000)


def initialize(db):
    for table in ("catalog_sets", "printings"):
        if "publication_state" not in {r[1] for r in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN publication_state TEXT NOT NULL DEFAULT 'published'")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS catalog_imports(
        id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),package TEXT NOT NULL,
        package_hash TEXT UNIQUE NOT NULL,set_id TEXT NOT NULL,state TEXT NOT NULL,
        baseline TEXT NOT NULL,preview TEXT NOT NULL,after_hash TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE IF NOT EXISTS catalog_heads(set_id TEXT PRIMARY KEY,import_id TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS catalog_audit(
        id INTEGER PRIMARY KEY,actor_id TEXT NOT NULL,event TEXT NOT NULL,object_id TEXT NOT NULL,
        detail TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE IF NOT EXISTS catalog_requests(
        id TEXT PRIMARY KEY,identity_key TEXT UNIQUE,state TEXT NOT NULL,decision TEXT NOT NULL DEFAULT '',
        revision INTEGER NOT NULL DEFAULT 0,merged_into TEXT REFERENCES catalog_requests(id));
      CREATE TABLE IF NOT EXISTS catalog_aliases(
        game TEXT NOT NULL,language TEXT NOT NULL,alias TEXT NOT NULL,identity_key TEXT NOT NULL,
        PRIMARY KEY(game,language,alias));
      CREATE TABLE IF NOT EXISTS catalog_submissions(
        id TEXT PRIMARY KEY,request_id TEXT NOT NULL REFERENCES catalog_requests(id),
        user_id TEXT NOT NULL REFERENCES users(id),origin TEXT NOT NULL,origin_id TEXT NOT NULL,
        hints TEXT NOT NULL,share_photos INTEGER NOT NULL DEFAULT 0,resolution_op TEXT,
        created TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,origin,origin_id));
    """)
    db.commit()


def admin(actor):
    if store.verified(actor).role != "owner":
        raise PermissionDenied


def audit(actor, event, key, detail):
    inv.execute(
        "INSERT INTO catalog_audit(actor_id,event,object_id,detail) VALUES(%s,%s,%s,%s)",
        [actor.user_id, event, key, encode(detail)],
    )


def normalized(value):
    return " ".join(value.casefold().split())


def identity(game, set_key, language):
    if (
        game not in ADAPTERS
        or not re.fullmatch(r"[a-z0-9-]{1,80}", set_key)
        or not re.fullmatch(r"[a-z-]{2,20}", language)
    ):
        raise ValueError("Use a supported game, canonical set key and language code")
    return game + ":" + language + ":" + set_key


def snapshot(set_id):
    return {
        "sets": store.rows("SELECT * FROM catalog_sets WHERE id=%s", [set_id]),
        "cards": store.rows("SELECT * FROM printings WHERE set_id=%s ORDER BY id", [set_id]),
        "head": store.rows("SELECT * FROM catalog_heads WHERE set_id=%s", [set_id]),
    }


def catalog_hash(value):
    # Rollback retains newly archived identities, which do not change active coverage.
    return fingerprint(
        {**value, "cards": [c for c in value["cards"] if c["publication_state"] == "published"]}
    )


def fingerprint(value):
    return digest(encode(value).encode())


def validate(raw):
    package = Package.model_validate(raw).model_dump()
    if package["reconcile_legacy_set"] is None:
        del package["reconcile_legacy_set"]
    else:
        from .catalog_reconcile import approved

        approved(package)
    for card in package["cards"]:
        for optional in ("legacy_id", "metadata"):
            if card[optional] is None:
                del card[optional]
        if card.get("legacy_id") and not package.get("reconcile_legacy_set"):
            raise ValueError("Legacy identities require explicit reviewed reconciliation")
    identity(package["game"], package["set_key"], package["language"])
    cards = package["cards"]
    if len(cards) > package["expected_count"] or (
        package["coverage"] == "catalog-entries" and len(cards) != package["expected_count"]
    ):
        raise ValueError("Declared coverage does not match the supplied checklist count")
    if len({c["external_id"] for c in cards}) != len(cards):
        raise ValueError("Repeated external identity")
    if len({(c["number"], c["edition"], c["finish"], c["variant"]) for c in cards}) != len(cards):
        raise ValueError("Repeated number/variant identity")
    if package["game"] == "synthetic-orbits":
        if any(
            not re.fullmatch(r"[A-Z]{2}-\d{3}/[A-Z]", c["number"])
            or c["variant"] not in {"orbit:plain", "orbit:nebula"}
            for c in cards
        ):
            raise ValueError("Synthetic Orbits uses AX-007/A style numbers and orbit:plain/nebula variants")
        if not package["set_name"].startswith("Synthetic "):
            raise ValueError("Synthetic catalogs must be visibly labeled")
    return package


def identity_rows(package, sid, provider, printing_ids=None):
    """Read identity guards in bounded batches; never retain them across calls."""
    mappings = {}
    existing = {r["id"]: r for r in store.rows("SELECT * FROM printings WHERE set_id=%s", [sid])}
    identities = {}
    for row in existing.values():
        key = tuple(row[k] for k in ("collector_number", "edition", "finish", "variant"))
        identities.setdefault(key, set()).add(row["id"])
    for offset in range(0, len(package["cards"]), 500):
        cards = package["cards"][offset : offset + 500]
        placeholders = ",".join(["%s"] * len(cards))
        mappings.update(
            (r["external_id"], r["internal_id"])
            for r in store.rows(
                "SELECT external_id,internal_id FROM external_mappings "
                f"WHERE provider=%s AND entity_kind='printing' AND external_id IN ({placeholders})",
                [provider, *[c["external_id"] for c in cards]],
            )
        )
        # IDs are global: retain the guard against repurposing an ID from another set.
        existing.update(
            (r["id"], r)
            for r in store.rows(
                f"SELECT * FROM printings WHERE id IN ({placeholders})",
                printing_ids[offset : offset + 500]
                if printing_ids is not None
                else [stable_id("catalog-printing", provider + ":" + c["external_id"]) for c in cards],
            )
        )
    return mappings, existing, identities


def rows_for(package):
    key = identity(package["game"], package["set_key"], package["language"])
    from . import catalog_reconcile

    sid = (
        catalog_reconcile.set_id(package)
        if package.get("reconcile_legacy_set")
        else stable_id("catalog-set", key)
    )
    gid = stable_id("game", package["game"])
    existing_game = store.rows("SELECT id FROM games WHERE game_key=%s", [package["game"]])
    if existing_game:
        gid = existing_game[0]["id"]
    setrow = dict(
        id=sid,
        game_id=gid,
        name=package["set_name"],
        language=package["language"],
        region=None,
        aliases=encode(package["aliases"]),
        release_metadata=encode(
            {"source_url": package["source_url"], "expected_count": package["expected_count"]}
        ),
        catalog_version=package["version"],
        coverage_status=package["coverage"],
        publication_state="published",
    )
    cards = []
    provider = package["provider"] + ":" + package["language"]
    reconciled = None
    if package.get("reconcile_legacy_set"):
        legacy_evidence = catalog_reconcile.identity_rows(package, sid)
        reconciled = [catalog_reconcile.printing(package, c, sid, legacy_evidence) for c in package["cards"]]
    batched = identity_rows(
        package, sid, provider, [pid for pid, _ in reconciled] if reconciled is not None else None
    )
    for index, c in enumerate(package["cards"]):
        pid = stable_id("catalog-printing", provider + ":" + c["external_id"])
        prior = None
        if reconciled is not None:
            pid, prior = reconciled[index]
            if prior:
                c = {**c, **{k: prior[k] for k in ("edition", "finish", "variant")}}
        mappings, existing, identities = batched
        mapping = [{"internal_id": mappings[c["external_id"]]}] if c["external_id"] in mappings else []
        key = tuple(c[k] for k in ("number", "edition", "finish", "variant"))
        same_identity = identities.get(key, set()) - {pid}
        old = [existing[pid]] if pid in existing else []
        if mapping and mapping[0]["internal_id"] != pid:
            raise ValueError("External identity is already mapped to a different printing")
        if same_identity:
            raise ValueError(
                "Printing identity already exists under a different source mapping; reconcile instead of duplicating"
            )
        if old and any(
            old[0][k] != v
            for k, v in {
                "set_id": sid,
                "collector_number": c["number"],
                "edition": c["edition"],
                "finish": c["finish"],
                "variant": c["variant"],
            }.items()
        ):
            raise ValueError("Identity conflict: an existing external ID cannot be repurposed")
        unresolved = [f for f in ("edition", "finish", "variant") if c[f] is None]
        cards.append(
            dict(
                id=pid,
                set_id=sid,
                collector_number=c["number"],
                language=package["language"],
                edition=c["edition"],
                finish=c["finish"],
                variant=c["variant"],
                unresolved_fields=prior["unresolved_fields"] if prior else encode(unresolved),
                attributes=encode(
                    {
                        "name": c["name"],
                        "game_key": package["game"],
                        "synthetic": ADAPTERS[package["game"]]["synthetic"],
                        "dex_eligible": False,
                        "supertype": "Unknown",
                        "rarity": "Unknown",
                        **c.get("metadata", {}),
                    }
                ),
                provenance=encode(
                    {
                        **(json.loads(prior["provenance"]) if prior else {}),
                        **({"legacy_id": c["legacy_id"]} if c.get("legacy_id") else {}),
                        "provider": provider,
                        "external_id": c["external_id"],
                        "source_version": package["version"],
                        "source_sha256": package["source_sha256"],
                    }
                ),
                publication_state="published",
            )
        )
    return setrow, cards


def get(actor, key):
    admin(actor)
    rows = store.rows("SELECT * FROM catalog_imports WHERE id=%s", [key])
    if not rows:
        raise Http404
    row = rows[0]
    for f in ("package", "baseline", "preview"):
        row[f] = json.loads(row[f])
    return row


@transaction.atomic
def preview(actor, raw):
    admin(actor)
    p = validate(raw)
    hashed = fingerprint(p)
    prior = store.rows("SELECT id FROM catalog_imports WHERE package_hash=%s", [hashed])
    if prior:
        return get(actor, prior[0]["id"])
    # Reusing a provider's version with different bytes is an error, not a new version.
    for old in store.rows("SELECT package FROM catalog_imports"):
        q = json.loads(old["package"])
        if (q["provider"], q["game"], q["set_key"], q["language"], q["version"]) == (
            p["provider"],
            p["game"],
            p["set_key"],
            p["language"],
            p["version"],
        ):
            raise ValueError("This source version already has different content; supply a new version")
    setrow, cards = rows_for(p)
    baseline = snapshot(setrow["id"])
    old = {c["id"]: c for c in baseline["cards"]}
    incoming = {c["id"]: c for c in cards}
    diff = {
        "added": [c for c in cards if c["id"] not in old],
        "updated": [
            {"before": old[c["id"]], "after": c} for c in cards if c["id"] in old and old[c["id"]] != c
        ],
        "archived": [
            c for c in baseline["cards"] if c["id"] not in incoming and c["publication_state"] == "published"
        ],
        "count": len(cards),
        "coverage": p["coverage"],
        "expected_count": p["expected_count"],
        "unresolved_variants": sum(bool(json.loads(c["unresolved_fields"])) for c in cards),
    }
    key = str(uuid.uuid4())
    inv.execute(
        "INSERT INTO catalog_imports(id,user_id,package,package_hash,set_id,state,baseline,preview) VALUES(%s,%s,%s,%s,%s,'preview',%s,%s)",
        [key, actor.user_id, encode(p), hashed, setrow["id"], encode(baseline), encode(diff)],
    )
    audit(actor, "import-preview", key, {"hash": hashed})
    return get(actor, key)


def write(table, row):
    columns = list(row)
    inv.execute(
        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))}) ON CONFLICT(id) DO UPDATE SET {','.join(k + '=excluded.' + k for k in columns if k != 'id')}",
        list(row.values()),
    )


def aliases(package):
    key = identity(package["game"], package["set_key"], package["language"])
    for value in [package["set_key"], package["set_name"], *package["aliases"]]:
        value = normalized(value)
        if not value or len(value) > 120:
            raise ValueError("Invalid reviewed alias")
        rows = store.rows(
            "SELECT identity_key FROM catalog_aliases WHERE game=%s AND language=%s AND alias=%s",
            [package["game"], package["language"], value],
        )
        if rows and rows[0]["identity_key"] != key:
            raise inv.Conflict("Reviewed alias already identifies another set")
        inv.execute(
            "INSERT INTO catalog_aliases VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            [package["game"], package["language"], value, key],
        )


@transaction.atomic
def transition(actor, key, action):
    op = get(actor, key)
    if action == "verify":
        if op["state"] == "verified":
            return op
        if op["state"] != "preview":
            raise ValueError("Verify a preview first")
        validate(op["package"])
        rows_for(op["package"])
        if catalog_hash(snapshot(op["set_id"])) != catalog_hash(op["baseline"]):
            raise inv.Conflict("Catalog changed after preview; create a new source version")
        inv.execute("UPDATE catalog_imports SET state='verified' WHERE id=%s", [key])
    elif action == "publish":
        if op["state"] == "published":
            return op
        if op["state"] not in {"verified", "rolled-back"}:
            raise ValueError("Verify before publishing")
        if catalog_hash(snapshot(op["set_id"])) != (
            op["after_hash"] if op["state"] == "rolled-back" else catalog_hash(op["baseline"])
        ):
            raise inv.Conflict("Catalog changed after verification; preview a new version")
        p = validate(op["package"])
        setrow, cards = rows_for(p)
        aliases(p)
        adapter = ADAPTERS[p["game"]]
        inv.execute(
            "INSERT INTO games VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            [
                setrow["game_id"],
                p["game"],
                adapter["name"],
                adapter["version"],
                encode(["catalog", "manual-entry"]),
                "synthetic" if adapter["synthetic"] else "local-pre-alpha",
            ],
        )
        mapping = store.rows(
            "SELECT internal_id FROM external_mappings WHERE provider=%s AND entity_kind='set' AND external_id=%s",
            [p["provider"] + ":" + p["language"], p["set_key"]],
        )
        if mapping and mapping[0]["internal_id"] != setrow["id"]:
            raise ValueError("Source set identity conflict")
        inv.execute(
            "INSERT INTO external_mappings VALUES(%s,'set',%s,%s) ON CONFLICT DO NOTHING",
            [p["provider"] + ":" + p["language"], p["set_key"], setrow["id"]],
        )
        if p.get("reconcile_legacy_set"):
            inv.execute(
                "INSERT INTO external_mappings VALUES('legacy','set',%s,%s) ON CONFLICT DO NOTHING",
                [p["reconcile_legacy_set"], setrow["id"]],
            )
        write("catalog_sets", setrow)
        inv.execute("UPDATE printings SET publication_state='archived' WHERE set_id=%s", [op["set_id"]])
        for row in cards:
            write("printings", row)
            provenance = json.loads(row["provenance"])
            inv.execute(
                "INSERT INTO external_mappings VALUES(%s,'printing',%s,%s) ON CONFLICT DO NOTHING",
                [provenance["provider"], provenance["external_id"], row["id"]],
            )
        inv.execute(
            "INSERT INTO catalog_heads VALUES(%s,%s) ON CONFLICT(set_id) DO UPDATE SET import_id=excluded.import_id",
            [op["set_id"], key],
        )
        inv.execute(
            "UPDATE catalog_imports SET state='published',after_hash=%s WHERE id=%s",
            [catalog_hash(snapshot(op["set_id"])), key],
        )
        inv.execute(
            "UPDATE catalog_requests SET state='published',revision=revision+1 WHERE identity_key=%s AND merged_into IS NULL",
            [identity(p["game"], p["set_key"], p["language"])],
        )
    elif action == "rollback":
        if op["state"] == "rolled-back":
            return op
        if op["state"] != "published" or catalog_hash(snapshot(op["set_id"])) != op["after_hash"]:
            raise inv.Conflict("Only the unchanged current publication can be rolled back")
        inv.execute("UPDATE printings SET publication_state='archived' WHERE set_id=%s", [op["set_id"]])
        inv.execute("UPDATE catalog_sets SET publication_state='archived' WHERE id=%s", [op["set_id"]])
        for row in op["baseline"]["sets"]:
            write("catalog_sets", row)
        for row in op["baseline"]["cards"]:
            write("printings", row)
        inv.execute("DELETE FROM catalog_heads WHERE set_id=%s", [op["set_id"]])
        for row in op["baseline"]["head"]:
            inv.execute("INSERT INTO catalog_heads VALUES(%s,%s)", [row["set_id"], row["import_id"]])
        inv.execute(
            "UPDATE catalog_imports SET state='rolled-back',after_hash=%s WHERE id=%s",
            [catalog_hash(snapshot(op["set_id"])), key],
        )
        p = op["package"]
        inv.execute(
            "UPDATE catalog_requests SET state='needs-evidence',decision='Coverage rolled back; your copy is retained',revision=revision+1 WHERE identity_key=%s AND merged_into IS NULL",
            [identity(p["game"], p["set_key"], p["language"])],
        )
    else:
        raise ValueError("Unsupported import action")
    audit(actor, "import-" + action, key, {})
    return get(actor, key)
