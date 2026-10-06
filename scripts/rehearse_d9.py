"""D9 retained-only publication on isolated disposable or complete copied state."""

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from backup_m6 import backup, dbhashes, filemap
from prepare_d9 import RETAINED, ROOT, write
from rehearse_m5 import files, snapshot


def run(root, output, mode):
    output.mkdir(parents=True, exist_ok=False)
    if mode == "disposable":
        from rehearse_m1 import run as prepare

        prepare(root, root.with_name(root.name + "-setup"))
    else:
        backup(RETAINED, root)
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model
    from django.test import RequestFactory
    from django.urls import resolve

    from pokemon_hunter.beta import catalog_imports as cat
    from pokemon_hunter.beta import catalog_pipeline as pipe
    from pokemon_hunter.beta import collection, store
    from pokemon_hunter.beta import collection_goals as cg
    from pokemon_hunter.beta import sealed_catalog as sealed

    actor = store.principal(1)
    pipe.initialize()
    order = [
        dict(path=f"config/sealed/{n}/package.json", service="sealed")
        for n in ["2026-10-04", "2026-10-04-151"]
    ]
    for s in json.loads((ROOT / "evidence/d8-20261006/publication-order.json").read_text())["order"]:
        order.append(
            dict(
                s,
                service="catalog"
                if s["step"] == 2
                else "pipeline"
                if s["step"] in [1, 4, 6, 10]
                else "sealed",
            )
        )
    services = {"catalog": cat, "pipeline": pipe, "sealed": sealed}

    def publish(service, raw):
        op = service.preview(actor, raw)
        assert op["state"] != "invalid", op
        if op["state"] == "preview":
            service.transition(actor, op["id"], "verify")
        while service.get(actor, op["id"])["state"] in ["verified", "partial"]:
            service.transition(actor, op["id"], "publish")
        assert service.get(actor, op["id"])["state"] == "published"
        stable = snapshot(root)
        assert service.preview(actor, raw)["id"] == op["id"]
        assert service.transition(actor, op["id"], "publish")["state"] == "published"
        assert snapshot(root) == stable
        return op["id"]

    if mode == "disposable":
        for s in order:
            publish(services[s["service"]], json.loads((ROOT / s["path"]).read_text()))
    before = snapshot(root)
    before_files = files(root)
    before_active = sealed.records()
    baseline = pipe.coverage(actor)
    assert baseline["totals"]["assessed"] == 48 and baseline["totals"]["target_numbered_count"] == 3104
    prerequisites = []
    for s in order:
        data = (ROOT / s["path"]).read_bytes()
        h = hashlib.sha256(data).hexdigest()
        if "sha256" in s:
            assert h == s["sha256"]
        op = services[s["service"]].preview(actor, json.loads(data))
        assert op["state"] == "published"
        prerequisites.append(
            dict(path=s["path"], sha256=h, journal_id=op["id"], state=op["state"], service=s["service"])
        )
    assert snapshot(root) == before
    write(output / "prerequisites.json", prerequisites)
    source = cg.latest(actor)
    assert len(cg.owned(source)) == 137 and len(cg.owned(source, 251)) == 161
    assert len(json.loads(source["reconciliation"])) == 286
    if mode == "copied-owner":
        assert len(before["owned_copies"]) == 207
    baseline_copy = root.with_name(root.name + "-baseline")
    restored_copy = root.with_name(root.name + "-restored")
    b = backup(root, baseline_copy)
    r = backup(baseline_copy, restored_copy)
    assert (
        b == r
        and dbhashes(root / "inventory.db") == dbhashes(restored_copy / "inventory.db")
        and filemap(root) == filemap(restored_copy)
    )
    write(
        output / "complete-root-restoration.json",
        dict(
            independent_restore=True,
            all_tables=len(b["database_tables"]),
            all_table_hashes_identical=True,
            all_file_bytes_identical=True,
            file_count=b["file_count"],
            opaque_config_preserved=True,
            distinct_from_supported_reversal=True,
        ),
    )
    catalog = json.loads((ROOT / "config/sealed/d9-20261006/catalog-package.json").read_text())
    batch = json.loads((ROOT / "config/catalog-pipeline/d9-20261006/batch.json").read_text())
    for label, bad in [
        (
            "invalid-reference",
            dict(
                catalog,
                printings=[dict(catalog["printings"][0], expansion_id="missing:exact")]
                + catalog["printings"][1:],
            ),
        ),
        (
            "stale-conflict",
            dict(
                catalog,
                corrections=[dict(catalog["corrections"][0], before_sha256="0" * 64)]
                + catalog["corrections"][1:],
            ),
        ),
    ]:
        stable = snapshot(root)
        try:
            sealed.preview(actor, bad)
        except (ValueError, collection.Conflict) as e:
            assert snapshot(root) == stable
            write(output / (label + ".json"), dict(error=str(e), no_partial_writes=True))
        else:
            raise AssertionError("Invalid package accepted")
    ops = []
    for name, service, raw, path in [
        ("sealed", sealed, catalog, "config/sealed/d9-20261006/catalog-package.json"),
        ("pipeline", pipe, batch, "config/catalog-pipeline/d9-20261006/batch.json"),
    ]:
        op = service.preview(actor, raw)
        write(output / (name + "-preview.json"), op)
        key = publish(service, raw)
        ops.append(
            dict(
                service=name,
                path=path,
                sha256=hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                journal_id=key,
            )
        )
    cov = pipe.coverage(actor)
    assert cov["totals"] == dict(
        sets=220,
        assessed=68,
        unassessed=152,
        target_numbered_count=3975,
        supplied_variant_records=6535,
        published_records=6535,
    ), cov["totals"]
    write(output / "coverage.json", cov)
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
    assert all(before[t] == after[t] for t in protected)
    assert before_files == files(root)
    for t in ["printings", "catalog_sets", "external_mappings"]:
        assert all(row in after[t] for row in before[t]), t
    active = sealed.records()
    for kind in sealed.KINDS:
        for k, v in before_active[kind].items():
            if kind == "expansions" and k in {e["id"] for e in catalog["expansions"]}:
                assert dict(active[kind][k], sources=v["sources"]) == v
            else:
                assert active[kind][k] == v, (kind, k)
    observation = next(
        o
        for o in active["observations"].values()
        if o.get("checked_at") == "2026-10-06T16:20:21.204089+00:00"
    )
    write(
        output / "preservation.json",
        dict(
            evidence_class=mode,
            protected_tables=protected,
            protected_rows_identical=True,
            all_predecessor_catalog_rows_identical=True,
            all_frozen_goal_save_auth_rows_identical=True,
            all_files_identical=True,
            kanto_owned=137,
            johto_owned=24,
            overall_owned=161,
            kanto_missing=14,
            overall_missing=90,
            marks=286,
            copies=len(before["owned_copies"]),
            token_observed_at=observation["checked_at"],
            provider_calls=0,
            owner_operated=False,
        ),
    )
    write(output / "operations.json", ops)
    # Current projection and complete initial-data responses; actual existing user,
    # in-process requests never create sessions or claim browser authentication.
    user = get_user_model().objects.get(pk=1)
    loading = []
    for name, urls in [
        ("pokedex", ["/pokedex/", "/api/collection/", "/api/parity/"]),
        ("combined", ["/lookup/?targets=123,134,196,197&scope=all"]),
    ]:
        entry = dict(
            flow=name,
            attempt=1,
            state="started",
            evidence_class=mode + " in-process complete responses",
            started_at=datetime.now(UTC).isoformat(),
        )
        loading.append(entry)
        write(output / "loading.json", loading)
        start = time.perf_counter()
        responses = []
        for url in urls:
            req = RequestFactory().get(url)
            req.user = user
            match = resolve(req.path)
            response = match.func(req, *match.args, **match.kwargs)
            assert response.status_code == 200
            body = response.content.decode()
            responses.append(
                dict(
                    url=url,
                    status=response.status_code,
                    bytes=len(response.content),
                    sha256=hashlib.sha256(response.content).hexdigest(),
                )
            )
            (output / (name + "-" + str(len(responses)) + ".response")).write_text(body)
            if url == "/api/parity/":
                data = json.loads(body)
                assert len(data["pokedex"]) == 251
                assert all(str(n) in data["pokedex"] for n in [123, 134, 196, 197])
            if name == "combined":
                assert all(n in body for n in ["Scyther", "Vaporeon", "Espeon", "Umbreon"])
        entry.update(
            state="complete", seconds=time.perf_counter() - start, responses=responses, deadline_seconds=21
        )
        write(output / "loading.json", loading)
        if entry["seconds"] > 21:
            write(
                output / "held.json",
                dict(
                    reason="complete response loading exceeds accepted 21 seconds",
                    flow=name,
                    seconds=entry["seconds"],
                    owner_operated=False,
                ),
            )
            raise AssertionError("Loading gate failed; retain expanded state and stop")
    assert snapshot(root) == after and files(root) == before_files
    # Owned and missing targets across both regions use current lookup while
    # all original goal definitions and frozen save bytes remain unchanged.
    expanded_receipt = backup(root, root.with_name(root.name + "-expanded"))
    write(
        output / "expanded-root.json",
        dict(all_tables=len(expanded_receipt["database_tables"]), files_identical=True),
    )
    for op in reversed(ops):
        services[op["service"]].transition(actor, op["journal_id"], "rollback")
    assert sealed.records() == before_active
    reversed_state = snapshot(root)
    assert all(before[t] == reversed_state[t] for t in protected) and files(root) == before_files
    for t in ["catalog_sets", "printings", "external_mappings", "catalog_heads"]:
        assert all(row in reversed_state[t] for row in before[t]), t
    write(
        output / "reversal.json",
        dict(
            reverse_order=[op["path"] for op in reversed(ops)],
            active_sealed_restored=True,
            original_catalog_rows_retained=True,
            protected_identical=True,
            audit_history_retained=True,
            complete_root_restoration_separate=True,
        ),
    )
    write(
        output / "result.json",
        dict(
            status="passed",
            evidence_class=mode,
            coverage=cov["totals"],
            idempotent=True,
            invalid_and_stale_refusal=True,
            preservation=True,
            rollback=True,
            restoration=True,
            loading=loading,
            provider_calls=0,
        ),
    )
    print(mode, "passed", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--mode", choices=["copied-owner", "disposable"], required=True)
    a = ap.parse_args()
    assert a.root.resolve() != Path("/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local")
    os.umask(0o077)
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No acquisition")),
        patch("httpx.AsyncClient.send", side_effect=AssertionError("No acquisition")),
        patch("urllib.request.urlopen", side_effect=AssertionError("No acquisition")),
        patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("No acquisition")),
    ):
        run(a.root, a.output, a.mode)
