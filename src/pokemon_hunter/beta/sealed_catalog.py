"""Public catalog metadata, immutable source observations and owner-reviewed publication.

Reviewed bridges publish compatible collection metadata in the same transaction.
Copies and frozen goals remain untouched. Descriptive corrections retain before/after
meaning and sources; identity changes require distinct records and mapping review.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from django.db import connection
from pydantic import BaseModel, ConfigDict, Field, field_validator

from pokemon_hunter.migration import encode

from . import canonical_species, store
from . import catalog_imports as cat
from . import collection as inv
from . import transactions as transaction


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Record(Model):
    id: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    sources: list[str] = Field(min_length=1)


class Source(Model):
    id: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9_.:-]+$")
    provider: str
    url: str
    retrieved_at: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    language: str | None
    market: str | None
    authority: Literal["official-species", "official-card", "official-product", "provider", "retailer"]
    status: Literal["usable", "access-denied", "unusable", "search-only"]
    subjects: list[str]
    supports: list[
        Literal[
            "species-identity",
            "printing-identity",
            "booster-membership",
            "distribution-membership",
            "product-identity",
            "product-contents",
            "offer-observation",
            "universe",
        ]
    ]
    rights: str
    note: str

    @field_validator("url")
    @classmethod
    def url_https(cls, value):
        if not re.fullmatch(r"https://[^\s]+", value):
            raise ValueError("Public HTTPS URL required")
        return value

    @field_validator("retrieved_at")
    @classmethod
    def dated(cls, value):
        instant(value)
        return value


class Species(Record):
    dex: int = Field(ge=1, le=100000)
    name: str = Field(min_length=1)


class Expansion(Record):
    name: str
    language: str
    series: str | None
    medium: Literal["physical", "digital", "unknown"]
    expected_printings: int | None = Field(ge=0)


class Printing(Record):
    expansion_id: str
    species_id: str | None
    name: str
    number: str
    language: str
    rarity: str | None
    finish: str | None
    variant: str | None
    category: Literal["pokemon", "trainer", "energy", "unknown"]


class Membership(Record):
    printing_id: str
    expansion_id: str
    status: Literal["booster", "promo", "deck-only", "unknown"]


class IncludedCard(Model):
    """Documented inclusion with unresolved exact printing; never target coverage."""

    name: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    canonical_dex: int | None = Field(default=None, ge=1)
    exact_printing: Literal["unresolved"]
    sources: list[str] = Field(min_length=1)


class Product(Record):
    name: str
    sku: str | None
    version: str = Field(min_length=1)
    market: str
    language: str
    product_type: str
    contents: Literal["complete", "mixed-known", "unknown"]
    total_packs: int | None = Field(ge=0)
    guaranteed_cards_known: bool
    included_cards: list[IncludedCard] = Field(default_factory=list)


class Pack(Record):
    product_id: str
    expansion_id: str | None
    quantity: int | None = Field(ge=1)


class Guaranteed(Record):
    product_id: str
    printing_id: str
    quantity: int = Field(ge=1)


class Offer(Record):
    product_id: str
    retailer: str
    seller: str | None
    seller_kind: Literal["direct", "marketplace", "unknown"]
    market: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    url: str

    _url = field_validator("url")(Source.url_https.__func__)


class Observation(Record):
    offer_id: str
    checked_at: str | None
    stock: Literal["in-stock", "out-of-stock", "preorder", "unknown"]
    price_minor: int | None = Field(ge=0)
    shipping_minor: int | None = Field(ge=0)
    note: str

    @field_validator("checked_at")
    @classmethod
    def observation_time(cls, value):
        if value is not None:
            instant(value)
        return value


class Mapping(Model):
    provider: str = Field(min_length=1)
    language: str = Field(min_length=2)
    kind: Literal["species", "expansions", "printings", "products", "offers"]
    external_id: str = Field(min_length=1)
    internal_id: str


class Coverage(Record):
    language: str
    market: str
    intended_expansions: list[str]
    species_count: int = Field(ge=1)
    gaps: list[str]


class Correction(Model):
    kind: str
    id: str
    before_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=1)


class BridgeLink(Model):
    printing_id: str
    external_id: str


class Bridge(Model):
    expansion_id: str
    package: cat.Package
    links: list[BridgeLink]


class Package(Model):
    schema_version: Literal["dex-sealed-v1"]
    provider: str = Field(min_length=1)
    version: str = Field(min_length=1)
    sources: list[Source]
    species: list[Species]
    expansions: list[Expansion]
    printings: list[Printing]
    memberships: list[Membership]
    products: list[Product]
    packs: list[Pack]
    guaranteed: list[Guaranteed]
    offers: list[Offer]
    observations: list[Observation]
    coverage: list[Coverage]
    mappings: list[Mapping]
    corrections: list[Correction] = Field(default_factory=list)
    bridges: list[Bridge] = Field(default_factory=list)


KINDS = (
    "sources",
    "species",
    "expansions",
    "printings",
    "memberships",
    "products",
    "packs",
    "guaranteed",
    "offers",
    "observations",
    "coverage",
)
# References are checked against the package plus published records, never archived imports.
REFS = {
    "printings": {"expansion_id": "expansions", "species_id": "species"},
    "memberships": {"printing_id": "printings", "expansion_id": "expansions"},
    "packs": {"product_id": "products", "expansion_id": "expansions"},
    "guaranteed": {"product_id": "products", "printing_id": "printings"},
    "offers": {"product_id": "products"},
    "observations": {"offer_id": "offers"},
}


def instant(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("A timezone-aware source time is required")
    return dt.astimezone(timezone.utc)


def initialize(db=None):
    """Additive, repeatable feature migration; compatible SQLite/PostgreSQL DDL."""
    statements = [
        "CREATE TABLE IF NOT EXISTS sealed_bridges(printing_id TEXT PRIMARY KEY,catalog_id TEXT NOT NULL,import_id TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS sealed_imports(id TEXT PRIMARY KEY,actor_id TEXT NOT NULL REFERENCES users(id),provider TEXT NOT NULL,version TEXT NOT NULL,package_hash TEXT UNIQUE NOT NULL,package TEXT NOT NULL,state TEXT NOT NULL,baseline TEXT NOT NULL,after_hash TEXT,UNIQUE(provider,version))",
        "CREATE TABLE IF NOT EXISTS sealed_mappings(provider TEXT NOT NULL,language TEXT NOT NULL,kind TEXT NOT NULL,external_id TEXT NOT NULL,internal_id TEXT NOT NULL,PRIMARY KEY(provider,language,kind,external_id))",
    ]
    for kind in KINDS:
        statements.append(
            f"CREATE TABLE IF NOT EXISTS sealed_{kind}(id TEXT PRIMARY KEY,data TEXT NOT NULL,publication_state TEXT NOT NULL CHECK(publication_state IN ('published','archived')))"
        )
    if db is not None:
        for sql in statements:
            db.execute(sql)
    else:
        with transaction.atomic(), connection.cursor() as c:
            for sql in statements:
                c.execute(sql)


def lock():
    # SQLite uses the application's IMMEDIATE transactions. Serialize PG catalog writers.
    if connection.vendor == "postgresql":
        inv.execute("LOCK TABLE sealed_imports IN EXCLUSIVE MODE")


def records(published=True):
    return {
        k: {
            r["id"]: json.loads(r["data"])
            for r in store.rows(
                f"SELECT * FROM sealed_{k}" + (" WHERE publication_state='published'" if published else "")
            )
        }
        for k in KINDS
    }


def validate(raw, existing=None):
    p = Package.model_validate(raw).model_dump()
    # Keep old product records and correction hashes byte-compatible.
    for product in p["products"]:
        if not product["included_cards"]:
            product.pop("included_cards")
    # Keep legacy package fingerprints stable when optional features are unused.
    if not p["corrections"]:
        p.pop("corrections")
    if not p["bridges"]:
        p.pop("bridges")
    allowed = {
        "species": {"name", "sources"},
        "expansions": {"name", "sources"},
        "printings": {"name", "rarity", "sources"},
        "products": {
            "name",
            "contents",
            "total_packs",
            "guaranteed_cards_known",
            "included_cards",
            "sources",
        },
        "packs": {"quantity", "sources"},
        "memberships": {"status", "sources"},
        "coverage": {"gaps", "sources"},
    }
    corrections = {}
    for c in p.get("corrections", []):
        key = (c["kind"], c["id"])
        if key in corrections or c["kind"] not in allowed:
            raise ValueError("Unsupported or repeated correction; observations need new IDs")
        old = (existing or {}).get(c["kind"], {}).get(c["id"])
        new = next((r for r in p[c["kind"]] if r["id"] == c["id"]), None)
        if not old or not new or cat.fingerprint(old) != c["before_sha256"]:
            raise inv.Conflict("Stale correction or missing published identity")
        changed = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
        if not changed or not changed <= allowed[c["kind"]]:
            raise ValueError(
                "Canonical identity conflict; requires new record/version and explicit mapping review"
            )
        if new["sources"] == old["sources"] or not set(old["sources"]) <= set(new["sources"]):
            raise ValueError("Correction must retain prior provenance and add source evidence")
        corrections[key] = c
    all_records = {k: dict((existing or {}).get(k, {})) for k in KINDS}
    for kind in KINDS:
        if len({r["id"] for r in p[kind]}) != len(p[kind]):
            raise ValueError("Repeated identity in " + kind)
        for r in p[kind]:
            old = all_records[kind].get(r["id"])
            if old is not None and old != r and (kind, r["id"]) not in corrections:
                raise ValueError("Immutable record conflict: " + r["id"])
            all_records[kind][r["id"]] = r

    def ref(kind, key):
        try:
            return all_records[kind][key]
        except KeyError as e:
            raise ValueError("Broken reference: " + kind + ":" + key) from e

    def authority(row, required, purpose_override=None, correction_kind=None):
        purpose = (
            purpose_override
            or {
                "official-species": "species-identity",
                "official-card": "booster-membership",
                "official-product": "product-contents",
                "retailer": "offer-observation",
            }[required]
        )
        source_ids = row["sources"]
        claims = {
            "memberships": {"status"},
            "packs": {"quantity"},
            "products": {"contents", "total_packs", "guaranteed_cards_known", "included_cards"},
        }
        if (correction_kind, row["id"]) in corrections:
            old = existing[correction_kind][row["id"]]
            if any(row.get(field) != old.get(field) for field in claims.get(correction_kind, set())):
                source_ids = list(set(source_ids) - set(old["sources"]))
        return any(
            (source := ref("sources", s))["authority"] == required
            and source["status"] == "usable"
            and row["id"] in source["subjects"]
            and (
                purpose in source["supports"]
                or (required == "official-card" and "distribution-membership" in source["supports"])
            )
            and (row.get("language") is None or source["language"] == row["language"])
            and (row.get("market") is None or source["market"] == row["market"])
            for s in source_ids
        )

    for kind in KINDS[1:]:
        for row in p[kind]:
            if len(set(row["sources"])) != len(row["sources"]):
                raise ValueError("Repeated provenance")
            for s in row["sources"]:
                ref("sources", s)
            for field, target in REFS.get(kind, {}).items():
                if row[field] is not None:
                    ref(target, row[field])
    for row in p["species"]:
        canonical_species.require(row["dex"])
        if row["id"] != f"ndex:{row['dex']:04}" or not authority(row, "official-species"):
            raise ValueError("Canonical species requires National Dex identity and official evidence")
    if len({r["dex"] for r in all_records["species"].values()}) != len(all_records["species"]):
        raise ValueError("Conflicting canonical species")
    identities = set()
    for row in all_records["printings"].values():
        expansion = ref("expansions", row["expansion_id"])
        if row["language"] != expansion["language"] or (row["species_id"] and row["category"] != "pokemon"):
            raise ValueError("Printing language/category identity conflict")
        key = tuple(row[f] for f in ("expansion_id", "number", "language", "finish", "variant"))
        if key in identities:
            raise ValueError("Repeated exact printing")
        identities.add(key)
    for row in p["memberships"]:
        printing = ref("printings", row["printing_id"])
        expansion = ref("expansions", row["expansion_id"])
        if printing["expansion_id"] != row["expansion_id"]:
            raise ValueError("Membership expansion mismatch")
        if row["status"] != "unknown" and (
            expansion["medium"] != "physical"
            or not authority(
                {**row, "language": printing["language"]},
                "official-card",
                correction_kind="memberships",
                purpose_override="distribution-membership"
                if row["status"] in {"promo", "deck-only"}
                else None,
            )
        ):
            raise ValueError(
                "Known distribution requires usable official card evidence and a physical expansion"
            )
    member_keys = [(r["printing_id"], r["expansion_id"]) for r in all_records["memberships"].values()]
    if len(member_keys) != len(set(member_keys)):
        raise ValueError("Conflicting membership")
    for row in p["packs"]:
        product = ref("products", row["product_id"])
        if row["expansion_id"]:
            ex = ref("expansions", row["expansion_id"])
            if ex["language"] != product["language"] or ex["medium"] != "physical":
                raise ValueError("Product pack language/medium mismatch")
        if row["quantity"] is not None and not authority(
            {**row, "language": product["language"], "market": product["market"]},
            "official-product",
            correction_kind="packs",
        ):
            raise ValueError("Known pack quantities require usable official contents evidence")
    for row in p["guaranteed"]:
        product = ref("products", row["product_id"])
        if (
            not authority(
                {**row, "market": product["market"], "language": product["language"]}, "official-product"
            )
            or ref("printings", row["printing_id"])["language"]
            != ref("products", row["product_id"])["language"]
        ):
            raise ValueError("Guaranteed card requires official product evidence and matching language")
    for row in p["products"]:
        for card in row.get("included_cards", []):
            if card["canonical_dex"] is not None:
                canonical_species.require(card["canonical_dex"])
            if len(card["sources"]) != len(set(card["sources"])) or not authority(
                dict(row, sources=card["sources"]), "official-product"
            ):
                raise ValueError("Included card requires exact official product applicability")
    product_keys = set()
    for row in all_records["products"].values():
        if row["sku"] is not None:
            key = (row["sku"], row["version"], row["market"], row["language"])
            if key in product_keys:
                raise ValueError("Repeated product version")
            product_keys.add(key)
        packs = [x for x in all_records["packs"].values() if x["product_id"] == row["id"]]
        if row["total_packs"] is not None and not authority(
            row, "official-product", correction_kind="products"
        ):
            raise ValueError("Product totals require official contents evidence")
        if row["contents"] != "unknown":
            if (
                (not packs and row["total_packs"] != 0)
                or any(x["quantity"] is None or x["expansion_id"] is None for x in packs)
                or row["total_packs"] != sum(x["quantity"] for x in packs)
                or not row["guaranteed_cards_known"]
                or not authority(row, "official-product", correction_kind="products")
            ):
                raise ValueError(
                    "Known contents require complete, official pack counts and guaranteed-card review"
                )
    for row in p["offers"]:
        product = ref("products", row["product_id"])
        if row["market"] != product["market"] or (row["seller_kind"] != "unknown" and not row["seller"]):
            raise ValueError("Offer market/seller mismatch")
    for row in p["observations"]:
        applicable = [ref("sources", s) for s in row["sources"]]
        offer = ref("offers", row["offer_id"])
        if not any(s["authority"] == "retailer" and s["market"] == offer["market"] for s in applicable):
            raise ValueError("Observation requires applicable retailer provenance")
        if row["checked_at"] is not None and any(
            instant(row["checked_at"]) > instant(s["retrieved_at"]) for s in applicable
        ):
            raise ValueError("Observation time cannot follow retained evidence retrieval")
        if (
            row["stock"] != "unknown" or row["price_minor"] is not None or row["shipping_minor"] is not None
        ) and not authority({**row, "market": offer["market"]}, "retailer"):
            raise ValueError("Known stock/price requires usable retailer evidence")
    observation_keys = [
        (r["offer_id"], instant(r["checked_at"]))
        for r in all_records["observations"].values()
        if r["checked_at"] is not None
    ]
    if len(observation_keys) != len(set(observation_keys)):
        raise ValueError("Conflicting dated observation")
    for row in p["coverage"]:
        if len(set(row["intended_expansions"])) != len(row["intended_expansions"]):
            raise ValueError("Repeated universe expansion")
        for key in row["intended_expansions"]:
            ex = ref("expansions", key)
            if ex["language"] != row["language"] or ex["medium"] != "physical":
                raise ValueError("Physical English universe identity mismatch")
        if row["species_count"] != len(all_records["species"]):
            raise ValueError("Species coverage count mismatch")
    mapping_keys = set()
    for row in p["mappings"]:
        target = ref(row["kind"], row["internal_id"])
        if target.get("language", row["language"]) != row["language"]:
            raise ValueError("Mapping language mismatch")
        key = tuple(row[k] for k in ("provider", "language", "kind", "external_id"))
        if key in mapping_keys:
            raise ValueError("Repeated external mapping")
        mapping_keys.add(key)
    from . import sealed_bridge

    for bridge in p.get("bridges", []):
        sealed_bridge.validate(p, bridge)
    return p


def check(raw):
    current = records()
    p = validate(raw, current)
    historical = records(False)
    for kind in KINDS:
        for row in p[kind]:
            if (
                row["id"] in historical[kind]
                and row != historical[kind][row["id"]]
                and (kind, row["id"]) not in {(c["kind"], c["id"]) for c in p.get("corrections", [])}
            ):
                raise ValueError("Archived identity cannot be repurposed")
    for m in p["mappings"]:
        old = store.rows(
            "SELECT internal_id FROM sealed_mappings WHERE provider=%s AND language=%s AND kind=%s AND external_id=%s",
            [m[k] for k in ("provider", "language", "kind", "external_id")],
        )
        if old and old[0]["internal_id"] != m["internal_id"]:
            raise ValueError("External identity mapping conflict")
    linked = {link["printing_id"] for b in p.get("bridges", []) for link in b["links"]}
    for c in p.get("corrections", []):
        if (
            c["kind"] == "printings"
            and store.rows("SELECT * FROM sealed_bridges WHERE printing_id=%s", [c["id"]])
            and c["id"] not in linked
        ):
            raise ValueError("Bridged printing correction requires atomic collection metadata review")
    return p


def snapshot():
    return {
        "records": records(False),
        "states": {k: store.rows(f"SELECT id,publication_state FROM sealed_{k} ORDER BY id") for k in KINDS},
        "mappings": store.rows("SELECT * FROM sealed_mappings ORDER BY provider,language,kind,external_id"),
        "published_imports": [
            r["id"] for r in store.rows("SELECT id FROM sealed_imports WHERE state='published' ORDER BY id")
        ],
    }


def publication_hash():
    # Reserved mappings and archived records survive rollback without changing active content.
    return cat.fingerprint(
        {
            "records": records(),
            "published_imports": [
                r["id"]
                for r in store.rows("SELECT id FROM sealed_imports WHERE state='published' ORDER BY id")
            ],
        }
    )


def get(actor, key):
    cat.admin(actor)
    rows = store.rows("SELECT * FROM sealed_imports WHERE id=%s", [key])
    if not rows:
        raise ValueError("Unknown sealed import")
    r = rows[0]
    r["package"] = json.loads(r["package"])
    r["baseline"] = json.loads(r["baseline"])
    return r


@transaction.atomic
def preview(actor, raw):
    cat.admin(actor)
    lock()
    p = Package.model_validate(raw).model_dump()
    for product in p["products"]:
        if not product["included_cards"]:
            product.pop("included_cards")
    for optional in ("corrections", "bridges"):
        if not p[optional]:
            p.pop(optional)
    hashed = cat.fingerprint(p)
    prior = store.rows("SELECT id FROM sealed_imports WHERE package_hash=%s", [hashed])
    if prior:
        return get(actor, prior[0]["id"])
    p = check(raw)
    if store.rows(
        "SELECT id FROM sealed_imports WHERE provider=%s AND version=%s", [p["provider"], p["version"]]
    ):
        raise ValueError("Source version already has different content")
    from . import sealed_bridge

    bridges = sealed_bridge.preview(actor, {**p, "bridges": p.get("bridges", [])})
    baseline = snapshot()
    baseline["bridges"] = bridges
    key = str(uuid.uuid4())
    inv.execute(
        "INSERT INTO sealed_imports VALUES(%s,%s,%s,%s,%s,%s,'preview',%s,NULL)",
        [key, actor.user_id, p["provider"], p["version"], hashed, encode(p), encode(baseline)],
    )
    cat.audit(actor, "sealed-preview", key, {"hash": hashed})
    return get(actor, key)


@transaction.atomic
def transition(actor, key, action):
    cat.admin(actor)
    lock()
    op = get(actor, key)
    state = op["state"]
    if (action, state) in {("verify", "verified"), ("publish", "published"), ("rollback", "rolled-back")}:
        return op
    expected = {"verify": "preview", "publish": "verified", "rollback": "published"}
    if expected.get(action) != state:
        raise ValueError("Preview, verify, publish and rollback in order")
    if action in {"verify", "publish"}:
        if snapshot() != {k: v for k, v in op["baseline"].items() if k != "bridges"}:
            raise inv.Conflict("Catalog changed; preview a fresh version")
        p = check(op["package"])
        from . import sealed_bridge

        sealed_bridge.transition(actor, op["baseline"].get("bridges", []), action)
        if action == "publish":
            for kind in KINDS:
                for row in p[kind]:
                    inv.execute(
                        f"INSERT INTO sealed_{kind} VALUES(%s,%s,'published') ON CONFLICT(id) DO UPDATE SET data=excluded.data,publication_state='published'",
                        [row["id"], encode(row)],
                    )
            for m in p["mappings"]:
                inv.execute(
                    "INSERT INTO sealed_mappings VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    [m[k] for k in ("provider", "language", "kind", "external_id", "internal_id")],
                )
    else:
        corrections = {(c["kind"], c["id"]) for c in op["package"].get("corrections", [])}
        if corrections:
            current = records()
            for kind in KINDS:
                for row in op["package"][kind]:
                    if current[kind].get(row["id"]) != row:
                        raise inv.Conflict("Conflicting reversal: later record changes retained")
            # A later publication using a newly added source/identity blocks archival.
            for later in store.rows(
                "SELECT package FROM sealed_imports WHERE state='published' AND id<>%s", [key]
            ):
                q = json.loads(later["package"])
                new_ids = {
                    r["id"]
                    for k in KINDS
                    for r in op["package"][k]
                    if r["id"] not in op["baseline"]["records"][k]
                }
                if any(s in new_ids for k in KINDS[1:] for r in q[k] for s in r["sources"]):
                    raise inv.Conflict("Later publication depends on corrected provenance")
        elif publication_hash() != op["after_hash"]:
            raise inv.Conflict("Only the unchanged current publication can be rolled back")
        from . import sealed_bridge

        sealed_bridge.transition(actor, list(reversed(op["baseline"].get("bridges", []))), "rollback")
        p = op["package"]
        for kind in KINDS:
            prior_states = {r["id"]: r["publication_state"] for r in op["baseline"]["states"][kind]}
            for row in p[kind]:
                if (kind, row["id"]) in corrections:
                    inv.execute(
                        f"UPDATE sealed_{kind} SET data=%s WHERE id=%s",
                        [encode(op["baseline"]["records"][kind][row["id"]]), row["id"]],
                    )
                inv.execute(
                    f"UPDATE sealed_{kind} SET publication_state=%s WHERE id=%s",
                    [prior_states.get(row["id"], "archived"), row["id"]],
                )
    inv.execute(
        "UPDATE sealed_imports SET state=%s WHERE id=%s",
        [{"verify": "verified", "publish": "published", "rollback": "rolled-back"}[action], key],
    )
    if action == "publish":
        inv.execute("UPDATE sealed_imports SET after_hash=%s WHERE id=%s", [publication_hash(), key])
    cat.audit(actor, "sealed-" + action, key, {})
    return get(actor, key)


@transaction.atomic
def report(actor, now=None):
    from . import offer_filters

    cat.admin(actor)
    lock()
    now = now or datetime.now(timezone.utc)
    current = records()
    counts = {k: len(v) for k, v in current.items()}
    coverage = []
    for row in current["coverage"].values():
        supplied = {r["expansion_id"] for r in current["printings"].values()}
        coverage.append(
            {
                **row,
                "sets_with_printings": len(set(row["intended_expansions"]) & supplied),
                "missing_sets": sorted(set(row["intended_expansions"]) - supplied),
            }
        )
    observations = []
    latest = {}
    for row in current["observations"].values():
        key = row["offer_id"]
        if key not in latest or offer_filters.observation_key(row) < offer_filters.observation_key(
            latest[key]
        ):
            latest[key] = row
    for row in current["observations"].values():
        fresh = offer_filters.age(row["checked_at"], now) == "fresh"
        offer = current["offers"][row["offer_id"]]
        observations.append(
            {
                **row,
                "fresh": fresh,
                "availability": "stale" if not fresh else row["stock"],
                "latest": latest[row["offer_id"]]["id"] == row["id"],
                "buy_now": latest[row["offer_id"]]["id"] == row["id"]
                and offer_filters.eligibility(
                    offer, row, current["products"][offer["product_id"]], current["sources"], now
                )["purchase_ready"],
            }
        )
    return {
        "schema_version": "dex-sealed-v1",
        "counts": counts,
        "printing_variants_normalized": counts["printings"],
        "numbered_checklist_identities": len(
            {(r["expansion_id"], r["number"], r["language"]) for r in current["printings"].values()}
        ),
        "canonical_mappings_resolved": sum(
            r["species_id"] is not None for r in current["printings"].values()
        ),
        "booster_memberships_evidenced": sum(
            r["status"] == "booster" for r in current["memberships"].values()
        ),
        "printings_bridged": store.rows(
            "SELECT b.* FROM sealed_bridges b JOIN sealed_printings s ON s.id=b.printing_id JOIN printings p ON p.id=b.catalog_id WHERE s.publication_state='published' AND p.publication_state='published'"
        ),
        "coverage": coverage,
        "unresolved_species_mappings": [
            r["id"]
            for r in current["printings"].values()
            if r["category"] == "pokemon" and r["species_id"] is None
        ],
        "unknown_contents": [r["id"] for r in current["products"].values() if r["contents"] == "unknown"],
        "observations": observations,
    }


def review(op):
    """A public-data review projection; never returns actor IDs or private baseline rows."""
    p = op["package"]
    return {
        "counts": {k: len(p[k]) for k in KINDS},
        "corrections": [
            {
                **c,
                "before": op["baseline"]["records"][c["kind"]][c["id"]],
                "after": next(r for r in p[c["kind"]] if r["id"] == c["id"]),
            }
            for c in p.get("corrections", [])
        ],
        "bridges": op["baseline"].get("bridges", []),
        "downstream": "Collection metadata only; no copy writes or frozen-goal enrollment. Structural verification is separate from source review and owner acceptance.",
        "new_records": {k: sum(r["id"] not in op["baseline"]["records"][k] for r in p[k]) for k in KINDS},
        "limited_sources": [
            {"id": s["id"], "status": s["status"], "note": s["note"]}
            for s in p["sources"]
            if s["status"] != "usable"
        ],
        "unknown_pack_counts": [r["id"] for r in p["packs"] if r["quantity"] is None],
        "unknown_stock": [r["id"] for r in p["observations"] if r["stock"] == "unknown"],
        "coverage_gaps": [gap for c in p["coverage"] for gap in c["gaps"]],
    }


def summary(result):
    lines = ["E1 public catalog coverage (published records only)"]
    lines += [f"{kind}: {count}" for kind, count in result["counts"].items()]
    for row in result["coverage"]:
        lines.append(
            f"{row['language']} / {row['market']}: {row['sets_with_printings']} of {len(row['intended_expansions'])} intended physical sets have E1 printings; {len(row['missing_sets'])} missing."
        )
        lines += ["Gap: " + gap for gap in row["gaps"]]
    lines.append(f"Unresolved species mappings: {len(result['unresolved_species_mappings'])}")
    lines.append(f"Unknown product contents: {len(result['unknown_contents'])}")
    for row in result["observations"]:
        lines.append(
            f"{row['offer_id']}: {row['availability']}; checked {row['checked_at']}; latest={row['latest']}; price={row['price_minor'] if row['price_minor'] is not None else 'unknown'} minor units; buy_now={row['buy_now']}"
        )
    lines.append(
        "Freshness is at most 24 hours from checked time; historical observations remain retained. Use report --json for every missing identity."
    )
    return "\n".join(lines)
