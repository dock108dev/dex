"""Exact D8-only copied-owner rehearsal and transaction-bound owner application."""

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from rehearse_m5 import digest, files, snapshot, write

PROJECT = Path(__file__).resolve().parents[1]


def run(root, output, expected=None, reverse=False):
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.test import RequestFactory
    from django.urls import resolve

    from pokemon_hunter.beta import catalog_imports as cat
    from pokemon_hunter.beta import catalog_pipeline as pipe
    from pokemon_hunter.beta import collection, lookup, store, transactions
    from pokemon_hunter.beta import collection_goals as cg
    from pokemon_hunter.beta import sealed_catalog as sealed

    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    actor = store.principal(1)
    before = snapshot(root)
    before_files = files(root)
    order = json.loads((PROJECT / "evidence/d8-20261006/publication-order.json").read_text())["order"]
    services = {"sealed": sealed, "pipeline": pipe, "catalog": cat}

    def state():
        return digest(
            dict(
                records=sealed.records(False),
                mappings=store.rows(
                    "SELECT * FROM sealed_mappings ORDER BY provider,language,kind,external_id"
                ),
                catalogs=store.rows("SELECT * FROM catalog_sets ORDER BY id"),
                printings=store.rows("SELECT * FROM printings ORDER BY id"),
                external=store.rows(
                    "SELECT * FROM external_mappings ORDER BY provider,entity_kind,external_id"
                ),
                heads=store.rows(
                    "SELECT h.set_id,i.package_hash FROM catalog_heads h JOIN catalog_imports i ON i.id=h.import_id ORDER BY h.set_id"
                ),
                sealed_journals=store.rows(
                    "SELECT package_hash,state FROM sealed_imports ORDER BY package_hash"
                ),
                batches=store.rows("SELECT package_hash,state FROM catalog_batches ORDER BY package_hash"),
            )
        )

    source = cg.latest(actor)
    assert source["source_sha256"] == "511dec82f4434e1e90ae27ec634e85e546f7559d43cc61d4cabec310d4ccc1b2"
    assert len(cg.owned(source)) == 137 and len(cg.owned(source, 251)) == 161
    assert len(before["owned_copies"]) == 207
    marks = json.loads(source["reconciliation"])
    assert len(marks) == 286
    assert (134 in cg.owned(source, 251)) and (123 not in cg.owned(source, 251))
    write(output / "before-tables.json", {t: dict(rows=len(v), sha256=digest(v)) for t, v in before.items()})
    baseline_hash = digest(before)
    if expected:
        assert baseline_hash == expected["baseline_all_tables_sha256"], (
            "Owner changed since immediate copied qualification"
        )
        assert before_files == expected["protected_files"], "Owner files changed since qualification"
    active_before = sealed.records()
    prerequisites = []
    operations = []
    loading = []
    with transactions.atomic():
        # Existing predecessors must be published, with no durable changes from inspection.
        for item in [
            dict(path=f"config/sealed/{n}/package.json", step=0) for n in ("2026-10-04", "2026-10-04-151")
        ] + order[:8]:
            raw = (PROJECT / item["path"]).read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            if "sha256" in item:
                assert sha == item["sha256"]
            service = cat if item["step"] == 2 else pipe if item["step"] in (1, 4, 6) else sealed
            op = service.preview(actor, json.loads(raw))
            assert op["state"] == "published", "Installed predecessor missing or incompatible"
            prerequisites.append(
                dict(path=item["path"], source_sha256=sha, journal_id=op["id"], state=op["state"])
            )
        assert snapshot(root) == before, "Prerequisite inspection changed owner data"
        if not expected:
            raw = json.loads((PROJECT / order[8]["path"]).read_text())
            for label, bad in [
                (
                    "exact-reference",
                    dict(
                        raw,
                        printings=[dict(raw["printings"][0], expansion_id="missing:exact")]
                        + raw["printings"][1:],
                    ),
                ),
                (
                    "stale-correction",
                    dict(
                        raw,
                        corrections=[dict(raw["corrections"][0], before_sha256="0" * 64)]
                        + raw["corrections"][1:],
                    ),
                ),
            ]:
                unchanged = snapshot(root)
                try:
                    sealed.preview(actor, bad)
                except (ValueError, collection.Conflict) as e:
                    assert snapshot(root) == unchanged
                    write(output / (label + "-refusal.json"), dict(error=str(e), no_partial_writes=True))
                else:
                    raise AssertionError("Invalid package unexpectedly accepted")
        for index, item in enumerate(order[8:]):
            raw = (PROJECT / item["path"]).read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            assert sha == item["sha256"]
            service_name = "pipeline" if item["step"] == 10 else "sealed"
            service = services[service_name]
            pre = state()
            if expected:
                gate = expected["operations"][index]
                assert (pre, sha, item["path"]) == (gate["before_hash"], gate["source_sha256"], gate["path"])
            op = service.preview(actor, json.loads(raw))
            write(output / f"preview-{index}.json", op)
            assert op["state"] != "invalid", "Exact ready package refused"
            reused = op["state"] == "published"
            if op["state"] == "preview":
                service.transition(actor, op["id"], "verify")
            while service.get(actor, op["id"])["state"] in ("verified", "partial"):
                service.transition(actor, op["id"], "publish")
            assert service.get(actor, op["id"])["state"] == "published"
            post = state()
            stable = snapshot(root)
            assert service.preview(actor, json.loads(raw))["id"] == op["id"]
            assert service.transition(actor, op["id"], "publish")["state"] == "published"
            assert state() == post and snapshot(root) == stable
            if expected:
                assert post == gate["after_hash"]
            operations.append(
                dict(
                    path=item["path"],
                    service=service_name,
                    source_sha256=sha,
                    before_hash=pre,
                    after_hash=post,
                    journal_id=op["id"],
                    reused=reused,
                )
            )
        cov = pipe.coverage(actor)
        assert cov["totals"] == dict(
            sets=220,
            assessed=48,
            unassessed=172,
            target_numbered_count=3104,
            supplied_variant_records=5067,
            published_records=5067,
        )
        write(output / "coverage.json", cov)
        if not expected:
            for number in (123, 134, 196, 197):
                start = time.monotonic()
                ctx = lookup.project(actor, dict(targets=str(number)))
                write(output / f"lookup-{number}.json", ctx)
                loading.append(dict(operation=f"lookup-{number}", seconds=time.monotonic() - start))
            # Actual view functions, existing owner identity, no fabricated login/session.
            user = get_user_model().objects.get(pk=1)
            for url in (
                "/pokedex/",
                "/api/parity/",
                "/catalog-coverage/",
                "/lookup/?targets=123,134,196,197",
            ):
                req = RequestFactory().get(url)
                req.user = user
                match = resolve(req.path)
                start = time.monotonic()
                response = match.func(req, *match.args, **match.kwargs)
                assert response.status_code == 200
                loading.append(
                    dict(
                        operation=url,
                        seconds=time.monotonic() - start,
                        status=response.status_code,
                        response_bytes=len(response.content),
                        evidence_class="in-process actual-owner-copy view, not browser authentication",
                    )
                )
        after = snapshot(root)
        allowed = {
            "catalog_sets",
            "printings",
            "external_mappings",
            "catalog_imports",
            "catalog_heads",
            "catalog_audit",
            "catalog_aliases",
            "catalog_batches",
            "collection_generations",
            "sqlite_sequence",
        }
        protected = [t for t in before if t not in allowed and not t.startswith("sealed_")]
        assert all(before[t] == after[t] for t in protected), "Protected owner rows changed"
        assert before_files == files(root), "Protected files changed"
        assert all(r in after["external_mappings"] for r in before["external_mappings"])
        assert {r[0] for r in before["printings"]} <= {r[0] for r in after["printings"]}
        observations = sealed.records()["observations"]
        assert all(observations[k] == v for k, v in active_before["observations"].items())
        if reverse:
            for op in reversed(operations):
                assert not op["reused"]
                services[op["service"]].transition(actor, op["journal_id"], "rollback")
            assert sealed.records() == active_before
            restored = snapshot(root)
            assert all(before[t] == restored[t] for t in protected)
            assert before_files == files(root)
            for t in ("catalog_sets", "printings", "external_mappings", "catalog_heads"):
                assert all(r in restored[t] for r in before[t]), "Predecessor active catalog row changed"
            write(
                output / "reversal.json",
                dict(
                    reverse_order=[op["path"] for op in reversed(operations)],
                    predecessor_active_sealed_restored=True,
                    predecessor_catalog_rows_retained=True,
                    protected_identical=True,
                ),
            )
        receipt = dict(
            accepted=True,
            evidence_class="installed-owner" if expected else "copied-owner",
            baseline_all_tables_sha256=baseline_hash,
            after_all_tables_sha256=digest(snapshot(root)),
            prerequisites=prerequisites,
            operations=operations,
            protected_tables=protected,
            protected_hashes={t: digest(before[t]) for t in protected},
            protected_files=before_files,
            before_counts={t: len(v) for t, v in before.items()},
            after_counts={t: len(v) for t, v in after.items()},
            loading=loading,
            source_sha256=source["source_sha256"],
            marks=286,
            copies=207,
            kanto_owned=137,
            johto_owned=24,
            overall_owned=161,
            kanto_missing=14,
            overall_missing=90,
            provider_calls=0,
            evaluated_at_utc=datetime.now(UTC).isoformat(),
        )
        write(output / "receipt.json", receipt)
        # Outer transaction rolls back all owner changes if any gate fails.
        assert not transaction.get_rollback()
    print("M6", receipt["evidence_class"], "passed", "with reversal" if reverse else "publication")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--expected", type=Path)
    ap.add_argument("--reverse", action="store_true")
    a = ap.parse_args()
    os.umask(0o077)
    with (
        patch("httpx.Client.send", side_effect=AssertionError("M6 acquisition forbidden")),
        patch("httpx.AsyncClient.send", side_effect=AssertionError("M6 acquisition forbidden")),
        patch("urllib.request.urlopen", side_effect=AssertionError("M6 acquisition forbidden")),
    ):
        run(a.root, a.output, json.loads(a.expected.read_text()) if a.expected else None, a.reverse)
