"""Disposable capture recovery tests; no customer roots or real transport."""

import hashlib
import io
import json
import os
from contextlib import contextmanager

import pytest
from tcgcsv_capture_helpers import batch as batch
from tcgcsv_capture_helpers import capture, envelope

from scripts import lv02_capture_plan as proposal
from scripts import tcgcsv_capture_history as history


def relocate(batch):
    path = batch["root"].parent / ".dex-tcgcsv-metadata/attempts.json"
    capture._private_directory(path.parent)
    batch["metadata"].rename(path)
    batch["metadata"] = path
    data = json.loads(path.read_bytes())
    data["attempts"][0]["plan"] = "tcgcsv-pokemon-groups-first-v1"
    capture._replace_metadata(path, data)
    return path


def run(batch, plan, bodies, *, stop_after=None):
    calls = []
    scope = proposal.scope_digest(plan)

    @contextmanager
    def transport(url, *, timeout):
        events = [
            json.loads(s)
            for s in (batch["accounting"] / ("batch-" + scope + ".jsonl")).read_text().splitlines()
        ]
        assert events[-1]["stage"] == "consumed" and events[-1]["attempt"] == len(calls) + 1
        assert json.loads(batch["metadata"].read_bytes())["attempts"][-1]["status"] == "consumed"
        index = len(calls)
        calls.append(url)
        body = bodies[index]
        stream = io.BytesIO(body)

        class Response:
            status = 200
            headers = {
                "content-type": "text/plain"
                if plan["steps"][index]["kind"] == "text"
                else "application/json",
                "content-length": str(len(body)),
            }

            def read(self, size, remaining):
                if stop_after == len(calls):
                    capture.request_stop(batch["root"])
                return stream.read(size)

        yield Response()

    result = capture.capture_batch(
        batch["root"],
        plan,
        expected_plan_sha256=capture.validate_batch_plan(plan, batch["root"]),
        open_response=transport,
        clock=batch["clock"],
        sleep=batch["clock"].sleep,
        now=lambda: "2026-11-06T12:00:00Z",
    )
    return result, calls


def first_stage(batch):
    relocate(batch)
    plan = proposal.prepare(batch["root"])
    body = envelope([dict(groupId=g["group_id"], categoryId=3, name=g["name"]) for g in proposal.GROUPS])
    result, calls = run(batch, plan, [b"2026-11-06T01:00:00Z", body])
    assert result["status"] == "captured" and len(calls) == 2
    return plan, body, result


def test_bootstrap_then_reviewed_group_capture_is_exactly_ten_attempts(batch):
    first, group_body, receipt = first_stage(batch)
    second = proposal.prepare(batch["root"], reviewed_groups_sha256=hashlib.sha256(group_body).hexdigest())
    assert first["limits"]["total_seconds"] + second["limits"]["total_seconds"] == 180
    bodies = [b"2026-11-06T01:00:00Z"]
    for g in proposal.GROUPS:
        bodies += [
            envelope(
                [
                    dict(
                        productId=g["group_id"],
                        categoryId=3,
                        groupId=g["group_id"],
                        name="Synthetic",
                        extendedData=[],
                    )
                ]
            ),
            envelope([dict(productId=g["group_id"], subTypeName="Normal", marketPrice=1)], total=False),
        ]
    bodies.append(bodies[0])
    result, calls = run(batch, second, bodies)
    assert result["status"] == "captured" and len(calls) == 8
    metadata = json.loads(batch["metadata"].read_bytes())
    assert len(metadata["attempts"]) == 3  # historical + exactly two reservations
    resource = {}
    history._history(batch["accounting"], batch["metadata"], resource_history=resource)
    assert not resource["unknown"] and set(resource["latest_by_group"]) == {3170, 604, 630, 635}
    with pytest.raises(capture.CaptureRefused, match="selected_groups_24h_reservation"):
        run(batch, second, bodies)


def test_no_dependent_plan_without_completed_metadata_review(batch):
    relocate(batch)
    with pytest.raises(FileNotFoundError):
        proposal.prepare(batch["root"], reviewed_groups_sha256="0" * 64)


@pytest.mark.parametrize("newer", [True, False])
def test_explicit_new_publication_metadata_preserves_history_and_refuses_replay(batch, newer):
    first, body, receipt = first_stage(batch)
    history_before = {p.name: p.read_bytes() for p in batch["accounting"].glob("*.jsonl")}
    plan = dict(
        first,
        plan_id="new-publication-metadata",
        refresh_cadence="metadata_new_build",
        timing_override="owner-new-publication-once",
    )
    build = b"2026-11-06T02:00:00Z" if newer else b"2026-11-06T01:00:00Z"
    result, calls = run(batch, plan, [build, body])
    assert all((batch["accounting"] / name).read_bytes() == raw for name, raw in history_before.items())
    assert len(calls) == (2 if newer else 1)
    assert result["status"] == ("captured" if newer else "stopped")
    if not newer:
        assert result["reason"] == "publisher_build_spacing" and result["retained_bodies"] == 0
    plan["plan_id"] = "display-name-cannot-renew"
    with pytest.raises(capture.CaptureRefused, match="timing_override_already_reserved"):
        run(batch, plan, [build, body])


def test_wrong_review_digest_and_replaced_retained_bytes_refused(batch):
    first, body, result = first_stage(batch)
    with pytest.raises(ValueError, match="review digest"):
        proposal.prepare(batch["root"], reviewed_groups_sha256="0" * 64)
    path = batch["root"] / result["capture_directory"] / "groups.json"
    changed = body + b" "
    path.write_bytes(changed)
    with pytest.raises(ValueError, match="review digest"):
        proposal.prepare(batch["root"], reviewed_groups_sha256=hashlib.sha256(changed).hexdigest())


def test_bootstrap_stop_consumes_and_cleans_without_replay(batch):
    relocate(batch)
    first = proposal.prepare(batch["root"])
    result, calls = run(batch, first, [b"2026-11-06T01:00:00Z"], stop_after=1)
    assert result["status"] == "stopped" and len(calls) == 1 and result["retained_bodies"] == 0
    assert json.loads(batch["metadata"].read_bytes())["attempts"][-1]["status"] == "stopped"
    capture.clear_stop(batch["root"])
    first["plan_id"] = "renamed-display-only"
    # Even beyond cadence, the same semantic selection remains consumed.
    with pytest.raises(capture.CaptureRefused, match="batch_already_consumed"):
        capture.capture_batch(
            batch["root"],
            first,
            expected_plan_sha256=capture.validate_batch_plan(first, batch["root"]),
            now=lambda: "2026-11-08T12:00:00Z",
            open_response=lambda *_a, **_k: pytest.fail("No replay"),
        )


@pytest.mark.parametrize(
    "mode", ["empty", "missing", "two_stores", "symlink", "hardlink", "fifo", "wrong_config"]
)
def test_existing_metadata_selection_fails_closed(batch, mode):
    path = relocate(batch)
    plan = proposal.prepare(batch["root"])
    if mode == "empty":
        capture._replace_metadata(path, {"schema": "dex-tcgcsv-metadata-attempts-v1", "attempts": []})
    elif mode == "missing":
        path.unlink()
    elif mode == "two_stores":
        other = batch["root"].parents[1] / ".dex-tcgcsv-metadata/attempts.json"
        capture._write_new(other, path.read_bytes())
    elif mode == "symlink":
        saved = path.with_name("saved.json")
        path.rename(saved)
        path.symlink_to(saved)
    elif mode == "hardlink":
        path.with_name("linked.json").hardlink_to(path)
    elif mode == "fifo":
        path.unlink()
        os.mkfifo(path, 0o600)
    elif mode == "wrong_config":
        plan["metadata_ledger_path"] = str(batch["root"].parents[1] / ".dex-tcgcsv-metadata/attempts.json")
    with pytest.raises((capture.CaptureRefused, OSError)):
        run(batch, plan, [])


def test_empty_in_memory_history_substitution_is_not_an_api(batch):
    with pytest.raises(TypeError):
        history._history(
            batch["accounting"],
            batch["metadata"],
            metadata_candidate={"schema": "dex-tcgcsv-metadata-attempts-v1", "attempts": []},
        )


@pytest.mark.parametrize("mode", ["symlink", "hardlink", "traversal", "digest"])
def test_retained_groups_safety_after_bootstrap(batch, mode):
    first, body, result = first_stage(batch)
    second = proposal.prepare(batch["root"], reviewed_groups_sha256=hashlib.sha256(body).hexdigest())
    path = batch["root"] / second["retained_groups_path"]
    if mode == "symlink":
        saved = path.with_name("saved.json")
        path.rename(saved)
        path.symlink_to(saved)
    elif mode == "hardlink":
        path.with_name("linked.json").hardlink_to(path)
    elif mode == "traversal":
        second["retained_groups_path"] = "price-snapshots/staging/../groups.json"
    else:
        second["retained_groups_sha256"] = "0" * 64
    with pytest.raises(capture.CaptureRefused):
        run(batch, second, [])


def test_bootstrap_cannot_hide_a_product_attempt_as_metadata_only(batch):
    first_stage(batch)
    path = next(batch["accounting"].glob("batch-*.jsonl"))
    events = [json.loads(s) for s in path.read_text().splitlines()]
    event = next(e for e in events if e["stage"] == "consumed")
    event.update(endpoint="products", group_id=604)
    path.write_bytes(b"".join(capture._json_bytes(e) for e in events))
    with pytest.raises(capture.CaptureRefused, match="invalid_accounting"):
        history._history(batch["accounting"], batch["metadata"])


def test_surviving_detailed_attempt_cannot_lose_metadata_reservation(batch):
    first_stage(batch)
    data = json.loads(batch["metadata"].read_bytes())
    data["attempts"].pop()
    capture._replace_metadata(batch["metadata"], data)
    with pytest.raises(capture.CaptureRefused, match="historical_metadata_reservations_missing"):
        history._history(batch["accounting"], batch["metadata"])


def test_metadata_plan_digest_must_match_surviving_detailed_selection(batch):
    first_stage(batch)
    data = json.loads(batch["metadata"].read_bytes())
    data["attempts"][-1]["manifest_sha256"] = "0" * 64
    capture._replace_metadata(batch["metadata"], data)
    with pytest.raises(capture.CaptureRefused, match="invalid_accounting"):
        history._history(batch["accounting"], batch["metadata"])


def test_bootstrap_obeys_daily_cadence_and_preexisting_stop(batch):
    relocate(batch)
    first = proposal.prepare(batch["root"])
    capture.request_stop(batch["root"])
    with pytest.raises(capture.CaptureRefused, match="stop_requested"):
        run(batch, first, [])
    capture.clear_stop(batch["root"])
    body = envelope([dict(groupId=g["group_id"], categoryId=3, name=g["name"]) for g in proposal.GROUPS])
    run(batch, first, [b"2026-11-06T01:00:00Z", body])
    changed = dict(first, not_before="2026-11-06T00:00:00Z", plan_id="different-window")
    with pytest.raises(capture.CaptureRefused, match="publisher_24h_reservation"):
        run(batch, changed, [])
