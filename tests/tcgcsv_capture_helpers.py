"""Fabricated capture fixtures shared by pilot, batch and cadence tests.

No live transport or customer-root access. This is not a collected test module.
"""

import importlib.util
import io
import json
from contextlib import contextmanager
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "capture_tcgcsv_snapshot", Path(__file__).parents[1] / "scripts" / "capture_tcgcsv_snapshot.py"
)
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)
BUILD = b"2026-10-17T12:30:00Z\n"


class Clock:
    def __init__(self):
        self.seconds = 0.0

    def __call__(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds


def envelope(rows, *, total=True):
    result = {"success": True, "errors": [], "results": rows}
    if total:
        result["totalItems"] = len(rows)
    return json.dumps(result).encode()


@pytest.fixture
def pilot(tmp_path):
    root = tmp_path / "customer"
    root.mkdir(mode=0o700)
    bodies = [
        BUILD,
        envelope([{"groupId": 3170, "categoryId": 3, "name": "SWSH12: Silver Tempest"}]),
        envelope(
            [{"productId": 1, "categoryId": 3, "groupId": 3170, "name": "Synthetic Card", "extendedData": []}]
        ),
        envelope([{"productId": 1, "subTypeName": "Normal", "marketPrice": 1.25}], total=False),
        BUILD,
    ]
    clock, calls, headers, statuses = Clock(), [], {}, {}

    @contextmanager
    def transport(url, *, timeout):
        index = len(calls)
        # The consumed record must already be durable and visible before dispatch.
        journal = next((root.parent / ".dex-tcgcsv-snapshots").rglob("*.jsonl"))
        events = [json.loads(line) for line in journal.read_text().splitlines()]
        assert events[-1]["stage"] == "consumed"
        assert events[-1]["attempt"] == index + 1
        assert 0 < timeout <= 15
        calls.append((url, clock()))
        body = bodies[index]
        stream = io.BytesIO(body)

        response_headers = {
            "content-type": "text/plain" if index in {0, 4} else "application/json",
            "content-length": str(len(body)),
        }
        response_headers.update(headers.get(index, {}))

        class Response:
            status = statuses.get(index, 200)
            headers = response_headers

            def read(self, size, remaining):
                assert 0 < remaining <= 15
                return stream.read(size)

        yield Response()

    def run(**extra):
        return capture.capture(
            root,
            open_response=transport,
            clock=clock,
            sleep=clock.sleep,
            now=lambda: "2026-10-17T13:00:00+00:00",
            **extra,
        )

    return dict(
        root=root, bodies=bodies, calls=calls, headers=headers, statuses=statuses, run=run, clock=clock
    )


@pytest.fixture
def batch(tmp_path):
    import hashlib

    owner = tmp_path / "owner"
    owner.mkdir(mode=0o700)
    root = owner / "customer"
    root.mkdir(mode=0o700)
    groups = [{"group_id": 1397, "name": "Aquapolis"}, {"group_id": 1375, "name": "Expedition"}]
    group_body = envelope([dict(groupId=g["group_id"], categoryId=3, name=g["name"]) for g in groups])
    retained = root / "price-snapshots/staging/hunt11/capture-v1/groups.json"
    capture._private_directory(retained.parent)
    capture._write_new(retained, group_body)
    plan = capture.make_batch_plan(
        root, groups, "2026-10-19T00:00:00Z", hashlib.sha256(group_body).hexdigest()
    )
    accounting = capture._accounting(root)
    legacy = [dict(stage="selected", maximum_attempts=5, at="2026-10-17T13:00:00Z")]
    for attempt in range(1, 6):
        legacy.append(dict(stage="consumed", attempt=attempt, at="2026-10-17T13:00:00Z"))
        if attempt in {1, 5}:
            legacy.append(dict(stage="received", attempt=attempt, publisher_built_at="2026-10-16T12:30:00Z"))
    legacy.append(dict(stage="closed", status="captured", consumed=5))
    capture._write_new(
        accounting / "hunt11-five-request-v1.jsonl", b"".join(capture._json_bytes(row) for row in legacy)
    )
    metadata = root.parents[1] / ".dex-tcgcsv-metadata/attempts.json"
    capture._private_directory(metadata.parent)
    capture._write_new(
        metadata,
        capture._json_bytes(
            dict(
                schema="dex-tcgcsv-metadata-attempts-v1",
                attempts=[
                    dict(
                        plan="historical-metadata",
                        manifest_sha256="a" * 64,
                        reserved_at="2026-10-17T12:00:00Z",
                        status="complete",
                    )
                ],
            )
        ),
    )
    build = b"2026-10-18T12:30:00Z\n"
    bodies = [build]
    for index, group in enumerate(groups):
        product_id = index + 1
        bodies.extend(
            [
                envelope(
                    [
                        dict(
                            productId=product_id,
                            categoryId=3,
                            groupId=group["group_id"],
                            name="Synthetic",
                            extendedData=[],
                        )
                    ]
                ),
                envelope([dict(productId=product_id, subTypeName="Normal", marketPrice=1.25)], total=False),
            ]
        )
    bodies.append(build)
    clock, calls, statuses, headers = Clock(), [], {}, {}

    @contextmanager
    def response(url, *, timeout):
        index = len(calls)
        journal = next(accounting.glob("batch-*.jsonl"))
        rows = [json.loads(line) for line in journal.read_text().splitlines()]
        assert rows[-1]["stage"] == "consumed" and rows[-1]["attempt"] == index + 1
        history = json.loads(metadata.read_bytes())
        assert history["attempts"][-1]["status"] == "consumed"
        assert history["attempts"][0]["plan"] in {"historical-metadata", "tcgcsv-pokemon-groups-first-v1"}
        assert 0 < timeout <= plan["limits"]["request_seconds"]
        calls.append((url, clock()))
        body = bodies[index]
        stream = io.BytesIO(body)
        response_headers = {
            "content-type": "text/plain" if index in {0, len(bodies) - 1} else "application/json",
            "content-length": str(len(body)),
        }
        response_headers.update(headers.get(index, {}))

        class Response:
            status = statuses.get(index, 200)
            headers = response_headers

            def read(self, size, remaining):
                return stream.read(size)

        yield Response()

    def run(**extra):
        return capture.capture_batch(
            root,
            plan,
            expected_plan_sha256=capture.validate_batch_plan(plan, root),
            open_response=extra.pop("open_response", response),
            clock=clock,
            sleep=clock.sleep,
            now=extra.pop("now", lambda: "2026-10-19T13:00:00Z"),
            **extra,
        )

    return dict(
        root=root,
        plan=plan,
        accounting=accounting,
        metadata=metadata,
        retained=retained,
        bodies=bodies,
        calls=calls,
        statuses=statuses,
        headers=headers,
        clock=clock,
        run=run,
    )
