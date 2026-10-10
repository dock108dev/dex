"""Synthetic fixture/server helpers; the superseded browser command is retired."""

import argparse
import json
import os
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
PASSWORD = "Synthetic-Shopping-Only-2026!"


def prepare(root, source):
    from pokemon_hunter.beta.cli import initialize, setup
    from pokemon_hunter.migration import import_snapshot

    (source / "config/catalog").mkdir(parents=True)
    (source / "data").mkdir()
    cards = {
        "synthetic-chansey": dict(name="Chansey", number="3", pokemon_dex=113, owned=False),
        "synthetic-scyther": dict(name="Scyther", number="10", pokemon_dex=123, owned=False),
        "synthetic-scyther-alt": dict(
            name="Rocket's Scyther", number="13", pokemon_dex=123, owned=True, first_edition=True
        ),
        "synthetic-bulbasaur": dict(name="Bulbasaur", number="44", pokemon_dex=1, owned=True),
    }
    for card in cards.values():
        card.update(set_id="synthetic", dex_eligible=True)
    (source / "config/pokedex_251.json").write_text(json.dumps(dict(cards=cards)))
    (source / "config/catalog/sources.json").write_text(
        json.dumps(dict(commit="synthetic", sets=[dict(id="synthetic", name="Synthetic Shopping Set")]))
    )
    (source / "config/settings.yaml").write_text("synthetic: true\n")
    with sqlite3.connect(source / "data/collection_hunts.db") as db:
        db.execute(
            "CREATE TABLE hunts(id INTEGER PRIMARY KEY,created TEXT,demo INTEGER,request TEXT,raw TEXT,coverage TEXT)"
        )
    database = source.parent / "synthetic.db"
    import_snapshot(source, database)
    initialize(root, database, b2=True, parity=True)
    (root / "SYNTHETIC_ONLY").write_text("Four indexed fixture printings; two synthetic accounts\n")
    setup(root)
    from django.core.management import call_command
    from django.db import connection

    from pokemon_hunter.beta import accounts, collection, shopping, store

    call_command("migrate", verbosity=0)
    owner = accounts.bootstrap(PASSWORD)
    member = accounts.invite("synthetic-member")
    from django.test import Client

    c = Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1:8011", REMOTE_ADDR="127.0.0.1")
    link = accounts.issue_link(member, "invite")
    redirected = c.get(link)
    assert redirected.status_code == 302
    c.get(redirected.url)
    redeemed = c.post(
        redirected.url,
        dict(
            new_password1=PASSWORD, new_password2=PASSWORD, csrfmiddlewaretoken=c.cookies["dex_b1_csrf"].value
        ),
    )
    assert redeemed.status_code == 302
    actor = store.principal(owner.pk)
    entries = collection.catalog(actor)
    alt = next(p for p in entries if p["name"] == "Rocket's Scyther")
    collection.execute(
        "UPDATE printings SET edition='first_edition',finish='holo',variant='first-edition',unresolved_fields='[]' WHERE id=%s",
        [alt["id"]],
    )
    collection.execute("UPDATE owned_copies SET provisional_identity='{}' WHERE printing_id=%s", [alt["id"]])
    for name, kind, extra in [
        ("Synthetic resolved species", "vintage", {}),
        ("Synthetic catalog association", "set", dict(set_id=alt["set_id"], policy="catalog")),
        ("Synthetic exact printings", "set", dict(set_id=alt["set_id"], policy="exact")),
    ]:
        op = collection.preview(actor, "goal", dict(name=name, goal_kind=kind, **extra), str(uuid.uuid4()))
        assert not op["plan"]["errors"]
        collection.confirm(actor, op["id"])
    before = collection.export_data(actor)
    shopping.initialize()
    shopping.initialize()
    assert collection.export_data(actor) == before
    guide = dict(
        card_id="synthetic-bulbasaur",
        value="2.550001",
        currency="USD",
        as_of="2026-09-27",
        edition="standard",
        grade="raw",
        grader="Guide",
        variant_verified=True,
        source_url="https://example.test/synthetic-guide",
        basis="Synthetic guide fixture",
    )
    (root / "parity-evidence/market_values.json").write_text(json.dumps([guide]))
    (root / "parity-evidence/raw_values.json").write_text("{}")
    (root / "protected.json").write_text(json.dumps(before, sort_keys=True))
    connection.close()


def serve(root, output, port):
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from serve_e4a import run

    from pokemon_hunter.beta import shopping

    with patch.object(
        shopping,
        "sources",
        lambda: (json.loads((root / "parity-evidence/market_values.json").read_text()), {}),
    ):
        run(root, output, port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--port", type=int, default=18173)
    args = parser.parse_args()
    os.environ["DEX_PROFILE"] = "local"
    if args.serve:
        serve(args.root, args.output, args.port)
    else:
        parser.error("Superseded Shopping browser journey removed; use current focused Shopping tests")
