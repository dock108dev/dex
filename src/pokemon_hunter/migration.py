"""Read-only legacy import into an explicitly supplied disposable inventory target."""

import hashlib
import json
import sqlite3
from pathlib import Path

from .inventory import OWNER_ID, connect, stable_id

VERSION = "b0-1"
SHARED_FIELDS = ("name", "rarity", "holo", "supertype", "pokemon_dex", "dex_eligible")
COPY_FIELDS = (
    "condition",
    "purchase_amount",
    "purchase_currency",
    "purchase_date",
    "notes",
    "grading_company",
    "grade",
    "certificate",
)


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(value).hexdigest()


def vintage_progress(cards):
    """Pokémon adapter goal only; never filters ordinary inventory."""
    species = {
        c["pokemon_dex"]
        for c in cards.values()
        if c.get("owned")
        and c.get("dex_eligible")
        and type(c.get("pokemon_dex")) is int
        and 1 <= c["pokemon_dex"] <= 251
    }
    return {
        "kanto": sum(1 <= n <= 151 for n in species),
        "johto": sum(152 <= n <= 251 for n in species),
        "total": len(species),
    }


def snapshot_files(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def import_snapshot(snapshot, target, user_id=OWNER_ID):
    snapshot, target = Path(snapshot).resolve(), Path(target).resolve()
    if target.is_relative_to(snapshot):
        raise ValueError("Target must be outside the read-only snapshot")
    files = snapshot_files(snapshot)
    data = json.loads(files["config/pokedex_251.json"])
    source_hash = digest(encode({p: digest(b) for p, b in files.items()}).encode())
    batch = stable_id("batch", f"{user_id}:{source_hash}")
    db = connect(target)
    with db:
        db.execute(
            "INSERT OR IGNORE INTO users VALUES(?,NULL,?,?,?)",
            (
                user_id,
                "admin" if user_id == OWNER_ID else None,
                "owner" if user_id == OWNER_ID else "member",
                "unprovisioned",
            ),
        )
        previous = db.execute("SELECT id FROM import_batches WHERE user_id=?", (user_id,)).fetchall()
        if any(r["id"] != batch for r in previous):
            raise ValueError("Changed snapshot requires explicit reconciliation; existing import preserved")
        db.execute(
            "INSERT OR IGNORE INTO import_batches VALUES(?,?,?,?,?)",
            (batch, user_id, source_hash, VERSION, "rehearsal"),
        )
        game = stable_id("game", "pokemon")
        db.execute(
            "INSERT OR IGNORE INTO games VALUES(?,?,?,?,?,?)",
            (game, "pokemon", "Pokémon", VERSION, encode(["catalog", "inventory"]), "local-rehearsal"),
        )
        sources = json.loads(files["config/catalog/sources.json"])
        for s in sources["sets"]:
            sid = stable_id("set", "pokemon:" + s["id"])
            db.execute(
                "INSERT OR IGNORE INTO catalog_sets VALUES(?,?,?,?,?,?,?,?,?)",
                (sid, game, s["name"], "en", None, "[]", "{}", sources["commit"], "legacy-snapshot"),
            )
            db.execute(
                "INSERT OR IGNORE INTO external_mappings VALUES(?,?,?,?)", ("legacy", "set", s["id"], sid)
            )
        for legacy, card in data["cards"].items():
            sid = stable_id("set", "pokemon:" + card["set_id"])
            edition = "first_edition" if card.get("first_edition") else None
            # The checkbox confirms first edition only. Unchecked does not prove unlimited/shadowless.
            unresolved = ["finish", "variant"] + ([] if edition else ["edition"])
            pid = stable_id("printing", f"pokemon:legacy:{legacy}:{edition or 'unresolved'}")
            attrs = {k: card[k] for k in SHARED_FIELDS if k in card}
            db.execute(
                "INSERT OR IGNORE INTO printings VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    pid,
                    sid,
                    str(card["number"]),
                    "en",
                    edition,
                    None,
                    None,
                    encode(unresolved),
                    encode(attrs),
                    encode(
                        {
                            "legacy_id": legacy,
                            "source_id": card.get("source_id"),
                            "catalog_commit": sources["commit"],
                        }
                    ),
                ),
            )
            for provider, key in [("legacy", legacy), ("pokemon-tcg-data", card.get("source_id"))]:
                if not key:
                    continue
                key = key + ":" + (edition or "unresolved")
                old = db.execute(
                    "SELECT internal_id FROM external_mappings WHERE provider=? AND entity_kind=? AND external_id=?",
                    (provider, "printing", key),
                ).fetchone()
                if old and old["internal_id"] != pid:
                    db.execute(
                        "INSERT OR IGNORE INTO migration_issues VALUES(?,?,?,?,?)",
                        (
                            stable_id("issue", f"{batch}:{legacy}:{provider}"),
                            batch,
                            legacy,
                            "conflicting-source-identity",
                            encode({"provider": provider, "key": key}),
                        ),
                    )
                else:
                    db.execute(
                        "INSERT OR IGNORE INTO external_mappings VALUES(?,?,?,?)",
                        (provider, "printing", key, pid),
                    )
            cid = None
            if card.get("owned"):
                cid = stable_id("copy", f"{user_id}:legacy:{legacy}")
                values = [card.get(k) for k in COPY_FIELDS]
                if values[1] is not None:
                    values[1] = str(values[1])
                db.execute(
                    """INSERT OR IGNORE INTO owned_copies
                    (id,user_id,printing_id,provisional_identity,condition,purchase_amount,purchase_currency,
                     purchase_date,notes,grading_company,grade,certificate,batch_id,legacy_id,first_edition_selected)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cid,
                        user_id,
                        pid,
                        encode({"unresolved_fields": unresolved}),
                        *values,
                        batch,
                        legacy,
                        int(bool(card.get("first_edition"))),
                    ),
                )
            db.execute(
                "INSERT OR IGNORE INTO import_records VALUES(?,?,?,?,?)",
                (batch, legacy, pid, cid, encode(card)),
            )
        for path, content in files.items():
            db.execute(
                "INSERT OR IGNORE INTO private_archives VALUES(?,?,?,?,?)",
                (batch, user_id, path, digest(content), content),
            )
        hunt = snapshot / "data/collection_hunts.db"
        if hunt.exists():
            with sqlite3.connect(f"{hunt.as_uri()}?mode=ro", uri=True) as source:
                for row in source.execute("SELECT id,created,demo,request,raw,coverage FROM hunts"):
                    db.execute(
                        "INSERT OR IGNORE INTO saved_hunts VALUES(?,?,?,?,?,?,?,?)", (batch, user_id, *row)
                    )
        db.execute(
            "INSERT OR IGNORE INTO goal_templates VALUES(?,?,?,?)",
            (
                "vintage-251",
                game,
                "legacy-v1",
                encode(
                    {
                        "adapter": "pokemon",
                        "eligibility": "legacy dex_eligible",
                        "range": [1, 251],
                        "exclusions": ["Dark", "trainer-owned", "Light", "Shining", "Trainer", "Energy"],
                        "inventory_filter": False,
                    }
                ),
            ),
        )
    db.close()
    return batch


def compare(snapshot, target, batch):
    files = snapshot_files(Path(snapshot))
    cards = json.loads(files["config/pokedex_251.json"])["cards"]
    db = connect(target)
    records = db.execute("SELECT * FROM import_records WHERE batch_id=?", (batch,)).fetchall()
    assert {r["legacy_id"]: json.loads(r["source_json"]) for r in records} == cards
    copies = {
        r["legacy_id"]: dict(r) for r in db.execute("SELECT * FROM owned_copies WHERE batch_id=?", (batch,))
    }
    assert set(copies) == {k for k, c in cards.items() if c.get("owned")}
    for legacy, c in cards.items():
        r = next(r for r in records if r["legacy_id"] == legacy)
        p = db.execute("SELECT * FROM printings WHERE id=?", (r["printing_id"],)).fetchone()
        assert p["collector_number"] == str(c["number"])
        assert p["set_id"] == stable_id("set", "pokemon:" + c["set_id"])
        assert json.loads(p["attributes"]) == {k: c[k] for k in SHARED_FIELDS if k in c}
        assert p["edition"] == ("first_edition" if c.get("first_edition") else None)
        if c.get("owned"):
            row = copies[legacy]
            assert row["printing_id"] == p["id"] and r["copy_id"] == row["id"]
            assert row["first_edition_selected"] == bool(c.get("first_edition"))
            for key in COPY_FIELDS:
                expected = c.get(key)
                if key == "purchase_amount" and expected is not None:
                    expected = str(expected)
                assert row[key] == expected, (legacy, key)
    archives = db.execute("SELECT * FROM private_archives WHERE batch_id=?", (batch,)).fetchall()
    assert {r["path"]: bytes(r["content"]) for r in archives} == files
    owner = db.execute("SELECT user_id FROM import_batches WHERE id=?", (batch,)).fetchone()[0]
    for table in ("owned_copies", "saved_hunts", "private_archives"):
        assert not db.execute(
            f"SELECT 1 FROM {table} WHERE batch_id=? AND user_id<>?", (batch, owner)
        ).fetchone()
    hunts = [
        tuple(r)
        for r in db.execute(
            "SELECT legacy_id,created,demo,request,raw,coverage FROM saved_hunts WHERE batch_id=? ORDER BY legacy_id",
            (batch,),
        )
    ]
    hp = Path(snapshot) / "data/collection_hunts.db"
    if hp.exists():
        with sqlite3.connect(f"{hp.resolve().as_uri()}?mode=ro", uri=True) as source:
            assert (
                hunts
                == source.execute(
                    "SELECT id,created,demo,request,raw,coverage FROM hunts ORDER BY id"
                ).fetchall()
            )
    imported = {
        r["legacy_id"]: {**json.loads(r["attributes"]), "owned": True}
        for r in db.execute(
            "SELECT c.legacy_id,p.attributes FROM owned_copies c JOIN printings p ON p.id=c.printing_id WHERE c.batch_id=? AND c.state='active'",
            (batch,),
        )
    }
    assert vintage_progress(imported) == vintage_progress(cards)
    report = {
        "exact_records": len(records),
        "owned_copies": len(copies),
        "first_edition": sum(c["first_edition_selected"] for c in copies.values()),
        "vintage_251": vintage_progress(imported),
        "saved_hunts": len(hunts),
        "archives": len(archives),
        "exact_comparison": "pass",
        "unresolved_owned": sum(
            bool(json.loads(c["provisional_identity"])["unresolved_fields"]) for c in copies.values()
        ),
        "identity_conflicts": db.execute(
            "SELECT count(*) FROM migration_issues WHERE batch_id=?", (batch,)
        ).fetchone()[0],
    }
    db.close()
    return report


def restore(target, batch, destination):
    """Reverse the snapshot mapping into a NEW directory, never the live checkout."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    db = connect(target)
    for row in db.execute("SELECT path,sha256,content FROM private_archives WHERE batch_id=?", (batch,)):
        p = destination / row["path"]
        if not p.resolve().is_relative_to(destination.resolve()):
            raise ValueError("Invalid archive path")
        assert digest(row["content"]) == row["sha256"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(row["content"])
    db.close()
