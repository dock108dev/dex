"""Captured finite Hunter traversal; provider pagination is never authority.

The request plan is independent of local catalog/reference coverage. Four
inclusive six-hour auction partitions intentionally overlap at their endpoints;
exact item/variation deduplication belongs to the leased run. BIN has no auction
end-time filter. A missing/changed provider total never proves market coverage.
"""

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from . import hunter_query

CUMULATIVE_SUMMARY_LIMIT = 2400
PAGE_COUNT_LIMIT = 12
PARTITION_COUNT_LIMIT = 8
PARTITION_DEPTH_LIMIT = 2
RETAINED_SUMMARY_LIMIT = 800
COMPARISON_CHUNK_LIMIT = 400
RESULT_RESPONSE_LIMIT = 200
ACTION_PAGE_LIMIT = 2
SCOPES = ("singles", "lots")
PLAN_SCOPES = (*SCOPES, "both")
LOT_CATEGORY = "183455"
# Explicit names for the run integration; these are separate from the fixed
# 400-summary sample and ordinary Shopping's unchanged limits.
MAX_CUMULATIVE_SUMMARIES = CUMULATIVE_SUMMARY_LIMIT
MAX_RETAINED_SUMMARIES = RETAINED_SUMMARY_LIMIT


@dataclass(frozen=True)
class Partition:
    id: str
    lane: str
    start: str
    end: str
    depth: int
    pages: int
    scope: str = "singles"


@dataclass(frozen=True)
class Request:
    plan_id: str
    scope: str
    lane: str
    start: str
    end: str
    window_start: str
    window_end: str
    partition_id: str
    partition_depth: int
    limit: int
    offset: int
    ordinal: int
    plan_scope: str | None = None


@dataclass(frozen=True)
class Plan:
    id: str
    scope: str
    start: str
    end: str
    partitions: tuple[Partition, ...]
    requests: tuple[Request, ...]

    def cursor(self, index=0):
        if type(index) is not int or not 0 <= index <= len(self.requests):
            raise ValueError("Choose a captured traversal cursor")
        if index == len(self.requests):
            return None
        digest = hashlib.sha256(f"{self.id}:{index}".encode()).hexdigest()[:24]
        return f"{index}:{digest}"

    def index(self, cursor):
        if not isinstance(cursor, str) or len(cursor) > 64:
            raise ValueError("Choose a captured traversal cursor")
        head, separator, _ = cursor.partition(":")
        if not separator or not re.fullmatch(r"0|[1-9][0-9]?", head):
            raise ValueError("Choose a captured traversal cursor")
        index = int(head)
        if index >= len(self.requests) or cursor != self.cursor(index):
            raise ValueError("The continuation does not belong to this plan")
        return index

    def request(self, cursor):
        return self.requests[self.index(cursor)]

    def next_cursor(self, cursor):
        return self.cursor(self.index(cursor) + 1)

    def public(self):
        return {
            "id": self.id,
            "scope": self.scope,
            "acquisition_scopes": list(dict.fromkeys(p.scope for p in self.partitions)),
            "start": self.start,
            "end": self.end,
            "pages": len(self.requests),
            "partitions": len(self.partitions),
            "partition_depth": max(p.depth for p in self.partitions),
            "limits": {
                "cumulative_summaries": CUMULATIVE_SUMMARY_LIMIT,
                "pages": PAGE_COUNT_LIMIT,
                "partitions": PARTITION_COUNT_LIMIT,
                "partition_depth": PARTITION_DEPTH_LIMIT,
                "retained_summaries": RETAINED_SUMMARY_LIMIT,
                "comparison_chunk": COMPARISON_CHUNK_LIMIT,
                "response_summaries": RESULT_RESPONSE_LIMIT,
                "action_pages": ACTION_PAGE_LIMIT,
                "page_summaries": hunter_query.PAGE_LIMIT,
                "page_bytes": hunter_query.RESPONSE_BYTE_LIMIT,
            },
            "coverage_complete": False,
        }


def build_plan(start, *, scope="singles", page_size=hunter_query.PAGE_LIMIT):
    if scope not in PLAN_SCOPES:
        raise ValueError("Choose singles, loose lots or their captured combined scope")
    if type(page_size) is not int or not 1 <= page_size <= hunter_query.PAGE_LIMIT:
        raise ValueError("Hunter pages contain between 1 and 200 summaries")
    start = hunter_query.utc_time(start)
    end = start + timedelta(hours=24)
    stamp = hunter_query._stamp
    window_start, window_end = stamp(start), stamp(end)
    partitions = tuple(
        Partition(
            f"auction-{index}",
            "auction",
            stamp(start + timedelta(hours=6 * index)),
            stamp(start + timedelta(hours=6 * (index + 1))),
            2,
            2,
            scope,
        )
        for index in range(4)
    ) + (Partition("bin-0", "buy_it_now", window_start, window_end, 0, 4, scope),)
    if scope == "both":
        # The composite plan retains every cap: two 12-hour auction partitions
        # per scope and one BIN partition per scope, with two pages each.
        parts = {}
        for actual_scope in SCOPES:
            parts[actual_scope] = tuple(
                Partition(
                    f"{actual_scope}-auction-{index}",
                    "auction",
                    stamp(start + timedelta(hours=12 * index)),
                    stamp(start + timedelta(hours=12 * (index + 1))),
                    1,
                    2,
                    actual_scope,
                )
                for index in range(2)
            ) + (
                Partition(
                    f"{actual_scope}-bin-0", "buy_it_now", window_start, window_end, 0, 2, actual_scope
                ),
            )
        partitions = (
            parts["singles"][0],
            parts["singles"][2],
            parts["lots"][0],
            parts["lots"][2],
            parts["singles"][1],
            parts["lots"][1],
        )
    identity = {
        "contract": "hunt-04-v1",
        "scope": scope,
        "start": window_start,
        "end": window_end,
        "page_size": page_size,
        "partitions": [p.__dict__ for p in partitions],
    }
    plan_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    # Every explicit action starts with one auction/BIN page where available.
    # The second pass visits each auction partition's remaining captured page.
    if scope == "both":
        sequence = [(partition, page) for page in range(2) for partition in partitions]
    else:
        sequence = []
        for index in range(4):
            sequence.extend(((partitions[index], 0), (partitions[-1], index)))
        sequence.extend((partition, 1) for partition in partitions[:-1])
    requests = tuple(
        Request(
            plan_id,
            partition.scope,
            partition.lane,
            partition.start,
            partition.end,
            window_start,
            window_end,
            partition.id,
            partition.depth,
            page_size,
            page * page_size,
            ordinal,
            scope,
        )
        for ordinal, (partition, page) in enumerate(sequence)
    )
    return Plan(plan_id, scope, window_start, window_end, partitions, requests)


def checked_request(request):
    """Rebuild the captured contract, so forged offsets/partitions fail closed."""
    if type(request) is not Request:
        raise ValueError("Choose an internally generated Hunter traversal request")
    if any(
        type(getattr(request, key)) is not int for key in ("ordinal", "limit", "offset", "partition_depth")
    ):
        raise ValueError("Traversal numeric bounds require exact integers")
    plan = build_plan(
        request.window_start, scope=request.plan_scope or request.scope, page_size=request.limit
    )
    if (
        type(request.ordinal) is not int
        or not 0 <= request.ordinal < len(plan.requests)
        or plan.requests[request.ordinal] != request
    ):
        raise ValueError("The traversal request does not match its captured plan")
    return request


def inspect_page(request, payload):
    """Bound and inspect hints without fetching or trusting any provider URL.

    A provider cursor which repeats or moves backwards is an explicit failure.
    A forward hint is advisory only: dispatch always uses the next captured
    request. Unexpected hint domains/filters cannot change the plan.
    """
    checked_request(request)
    if not isinstance(payload, dict):
        raise ValueError("Choose a bounded Hunter page")
    rows = payload.get("itemSummaries", [])
    if not isinstance(rows, list) or len(rows) > request.limit or any(not isinstance(r, dict) for r in rows):
        raise ValueError("Hunter page exceeds its summary bound")
    if "offset" in payload and (type(payload["offset"]) is not int or payload["offset"] != request.offset):
        raise ValueError("Provider cursor did not advance as requested")
    hint = payload.get("next")
    if hint is not None and (not isinstance(hint, str) or len(hint) > 8192):
        raise ValueError("Malformed provider pagination hint")
    if hint:
        try:
            offsets = parse_qs(urlsplit(hint).query).get("offset", [])
        except ValueError:
            raise ValueError("Malformed provider pagination hint") from None
        if offsets and (
            len(offsets) != 1
            or not re.fullmatch(r"[0-9]{1,5}", offsets[0])
            or int(offsets[0]) <= request.offset
        ):
            raise ValueError("Provider cursor repeated or did not advance")
    total = payload.get("total")
    total = total if type(total) is int and total >= 0 else None
    return {
        "received": len(rows),
        "total_reported": total,
        "has_provider_next": bool(hint),
        "total_inconsistent": total is not None and total < request.offset + len(rows),
        "truncated": bool(hint)
        or len(rows) == request.limit
        or (total is not None and total > request.offset + len(rows)),
        "reason": "provider_hints_are_advisory",
    }


@dataclass
class Progress:
    """Single-run claim/publication guard; durable budget also guards workers.

    Failed/in-flight pages remain attempted. A failure is terminal for this
    progress object, and Stop prevents a late completion from publishing.
    """

    plan: Plan
    index: int = 0
    fetched: int = 0
    attempted: int = 0
    completed: int = 0
    truncated: int = 0
    skipped: int = 0
    stopped: bool = False
    failed: bool = False
    pending: str | None = None
    observations: list = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @property
    def cursor(self):
        return self.plan.cursor(self.index)

    def claim(self, cursor):
        with self.lock:
            if self.stopped or self.failed or self.pending is not None or cursor != self.cursor:
                raise ValueError("The traversal cursor is no longer dispatchable")
            request = self.plan.request(cursor)
            self.pending = cursor
            self.attempted += 1
            return request

    def publish(self, cursor, payload):
        with self.lock:
            if self.stopped or self.failed or self.pending != cursor:
                raise ValueError("The traversal page is no longer publishable")
            try:
                hint = inspect_page(self.plan.request(cursor), payload)
                if self.fetched + hint["received"] > CUMULATIVE_SUMMARY_LIMIT:
                    raise ValueError("Traversal reached its cumulative summary limit")
            except ValueError:
                self.failed = True
                raise
            self.fetched += hint["received"]
            self.completed += 1
            self.truncated += int(hint["truncated"])
            self.observations.append(hint)
            self.pending = None
            self.index += 1
            return self.cursor

    def fail(self, cursor):
        with self.lock:
            if self.pending != cursor:
                raise ValueError("The traversal cursor is no longer active")
            self.failed = True

    def stop(self):
        with self.lock:
            self.stopped = True

    def coverage(self):
        with self.lock:
            return {
                "fetched": self.fetched,
                "attempted_pages": self.attempted,
                "completed_pages": self.completed,
                "remaining_pages": len(self.plan.requests) - self.index,
                "remaining_summaries_upper_bound": max(0, CUMULATIVE_SUMMARY_LIMIT - self.fetched),
                "truncated_pages": self.truncated,
                "skipped": self.skipped,
                "coverage_complete": False,
                "reasons": [
                    "finite_captured_plan",
                    "provider_hints_are_advisory",
                    "market_changes_during_traversal",
                ],
            }
