"""Create an entirely synthetic, private staging seed. Never reads owner data."""

import argparse
import io
import json
import os
import secrets
import sqlite3
import uuid
from pathlib import Path


def prepare(root):
    os.umask(0o077)
    os.environ["DEX_PROFILE"] = "local"
    from pokemon_hunter.inventory import connect

    from . import catalog_imports as cat
    from . import cli, scans

    cli.initialize(root, b2=True)
    with connect(root / "inventory.db") as db:
        scans.initialize(db)
        cat.initialize(db)
    for marker in ("B3_ISOLATED", "B4_ISOLATED", "B2_PARITY_ISOLATED"):
        (root / marker).write_text("SYNTHETIC staging rehearsal only\n")
    cfg = {"enabled": True, "mode": "fixture", "ceiling_usd": 1.0, "user_ceiling_usd": 0.5}
    (root / "scan-config.json").write_text(json.dumps(cfg))
    cli.setup(root)
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.core.management import call_command
    from django.db import connection
    from PIL import Image, ImageDraw

    from . import accounts, store
    from . import catalog_requests as req
    from . import collection as inv
    from .catalog_reconcile import PACKAGES

    call_command("migrate", verbosity=0)
    credentials = {"admin": secrets.token_urlsafe(24), "synthetic-member": secrets.token_urlsafe(24)}
    owner = accounts.bootstrap(credentials["admin"])
    member = accounts.invite("synthetic-member")
    member.set_password(credentials["synthetic-member"])
    member.save()
    inv.execute("UPDATE users SET state='active' WHERE auth_subject=%s", [str(member.pk)])
    actor = store.principal(owner.pk)
    other = store.principal(member.pk)

    def publish(path):
        op = cat.preview(actor, json.loads(path.read_text()))
        cat.transition(actor, op["id"], "verify")
        return cat.transition(actor, op["id"], "publish")

    for path in sorted(PACKAGES.glob("*.json")):
        if path.name not in {"source-manifest.json", "species.json"}:
            publish(path)
    publish(PACKAGES.parent / "gym-heroes.json")
    orbit = publish(PACKAGES.parent / "synthetic-orbits.json")
    cat.transition(actor, orbit["id"], "rollback")
    cat.transition(actor, orbit["id"], "publish")
    gid = store.rows("SELECT id FROM games WHERE game_key='pokemon'")[0]["id"]
    inv.execute(
        "INSERT INTO goal_templates VALUES(%s,%s,%s,%s)",
        [
            "vintage-251",
            gid,
            "synthetic-staging-v1",
            json.dumps({"species": "1-251", "eligibility": "reviewed normal Pokemon only"}),
        ],
    )

    def apply(who, kind, data):
        op = inv.preview(who, kind, data, str(uuid.uuid4()))
        return inv.confirm(who, op["id"])

    entries = inv.catalog(actor)
    for who in (actor, other):
        for _ in range(2):
            apply(
                who,
                "add",
                {
                    "printing_id": entries[0]["id"],
                    "duplicate_policy": "allow",
                    "attributes": {
                        "notes": "SYNTHETIC staging copy",
                        "purchase_amount": "0.100001",
                        "purchase_currency": "USD",
                    },
                },
            )
        apply(who, "goal", {"goal_kind": "vintage", "name": "Synthetic Vintage 251"})
        apply(
            who,
            "goal",
            {"goal_kind": "set", "set_id": entries[0]["set_id"], "name": "Synthetic set checklist"},
        )
        picture = Image.new("RGB", (600, 400), "#193344")
        ImageDraw.Draw(picture).text((25, 25), "SYNTHETIC - NOT A CARD", fill="white")
        out = io.BytesIO()
        picture.save(out, format="PNG")
        job = scans.create(
            who,
            str(uuid.uuid4()),
            [SimpleUploadedFile("synthetic.png", out.getvalue(), content_type="image/png")],
            "unsupported",
        )
        scans.process_one()
        job = scans.action(who, job["id"], "confirm", {"notes": "Synthetic provisional photo entry"})
        req.create(
            who,
            {
                "origin": "copy",
                "origin_id": job["copy_id"],
                "share_photos": who == other,
                "hints": {"game": "pokemon", "set": "Synthetic unavailable set", "language": "en"},
            },
        )
    # Deliberately retained interrupted reservation verifies rollback never refunds it.
    inv.execute("UPDATE scan_jobs SET reserved_usd=0.05 WHERE id=%s", [job["id"]])
    evidence = root / "parity-evidence"
    evidence.mkdir(mode=0o700)
    (evidence / "species.json").write_bytes((PACKAGES / "species.json").read_bytes())
    connection.close()
    with (
        sqlite3.connect(root / "inventory.db") as source,
        sqlite3.connect(root / "synthetic.copied.sqlite3") as dest,
    ):
        source.backup(dest)
    (root / "synthetic.copied.scan-config.json").write_text(json.dumps(cfg))
    (root / "credentials.json").write_text(json.dumps(credentials))
    (root / "SYNTHETIC_ONLY").write_text(
        "Generated accounts, collection, photos, requests and history; no owner data.\n"
    )
    print("Synthetic seed prepared. Credentials are in the private output directory; no links sent.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    prepare(parser.parse_args().output.resolve())
