"""Pure snapshot capture contracts: exact plans, limits and response schemas.

No transport, file writes or authority selection. Historical identifiers and
serialized plan digests remain unchanged when orchestration imports this policy.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

MIB = 1024 * 1024

BODY_LIMIT = 8 * MIB

ROW_LIMIT = 10000

STEPS = (
    ("build-before.txt", "https://tcgcsv.com/last-updated.txt", 1024, "text"),
    ("groups.json", "https://tcgcsv.com/tcgplayer/3/groups", BODY_LIMIT, "groups"),
    ("products.json", "https://tcgcsv.com/tcgplayer/3/3170/products", BODY_LIMIT, "products"),
    ("prices.json", "https://tcgcsv.com/tcgplayer/3/3170/prices", BODY_LIMIT, "prices"),
    ("build-after.txt", "https://tcgcsv.com/last-updated.txt", 1024, "text"),
)


class CaptureRefused(ValueError):
    """A sanitized reason code, never response contents or transport details."""


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CaptureRefused("duplicate_json_key")
        result[key] = value
    return result


def _nonfinite(_):
    raise CaptureRefused("nonfinite_json_number")


def _validate(body, kind, *, group_id=3170, groups=None):
    if kind == "text":
        try:
            text = body.decode("utf-8").strip()
            built = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (UnicodeError, ValueError):
            raise CaptureRefused("invalid_build_timestamp") from None
        aware = built.tzinfo is not None and built.utcoffset() is not None
        return {
            "publisher_build_text": text,
            "publisher_built_at": built.astimezone(timezone.utc).isoformat() if aware else None,
            "publisher_timezone_known": aware,
        }
    try:
        value = json.loads(
            body, object_pairs_hook=_unique_object, parse_constant=_nonfinite, parse_float=Decimal
        )
    except (UnicodeError, ValueError, RecursionError):
        raise CaptureRefused("invalid_json") from None
    expected = {"success", "errors", "results"}
    if kind != "prices":
        expected.add("totalItems")
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or value["success"] is not True
        or value["errors"] != []
        or not isinstance(value["results"], list)
        or len(value["results"]) > ROW_LIMIT
        or any(not isinstance(row, dict) for row in value["results"])
    ):
        raise CaptureRefused("invalid_envelope")
    rows = value["results"]
    if kind != "prices" and (type(value["totalItems"]) is not int or value["totalItems"] != len(rows)):
        raise CaptureRefused("inconsistent_row_count")
    if kind == "groups":
        bindings = groups or [{"group_id": 3170, "name": "SWSH12: Silver Tempest"}]
        for binding in bindings:
            matches = [row for row in rows if row.get("groupId") == binding["group_id"]]
            if (
                len(matches) != 1
                or type(matches[0].get("groupId")) is not int
                or type(matches[0].get("categoryId")) is not int
                or matches[0]["categoryId"] != 3
                or matches[0].get("name") != binding["name"]
            ):
                raise CaptureRefused("group_binding_conflict")
        matches = [row for row in rows if row.get("groupId") == bindings[0]["group_id"]]
        if (
            len(matches) != 1
            or type(matches[0].get("groupId")) is not int
            or type(matches[0].get("categoryId")) is not int
            or matches[0]["categoryId"] != 3
            or matches[0].get("name") != bindings[0]["name"]
        ):
            raise CaptureRefused("group_binding_conflict")
    seen = set()
    if kind in {"products", "prices"}:
        for row in rows:
            product_id = row.get("productId")
            if type(product_id) is not int or not 0 < product_id <= 2147483647:
                raise CaptureRefused("invalid_product_identity")
            if kind == "products":
                if (
                    type(row.get("categoryId")) is not int
                    or row["categoryId"] != 3
                    or type(row.get("groupId")) is not int
                    or row["groupId"] != group_id
                    or not isinstance(row.get("name"), str)
                    or not row["name"].strip()
                    or not isinstance(row.get("extendedData"), list)
                    or len(row["extendedData"]) > 100
                ):
                    raise CaptureRefused("product_binding_conflict")
                identity = product_id
            else:
                subtype = row.get("subTypeName")
                if not isinstance(subtype, str) or not subtype.strip() or len(subtype) > 2000:
                    raise CaptureRefused("invalid_literal_subtype")
                identity = (product_id, subtype)
            if identity in seen:
                raise CaptureRefused("duplicate_record_identity")
            seen.add(identity)
    return {"rows": len(rows)}


BATCH_LIMITS = {
    "file_bytes": 16 * MIB,
    "aggregate_input_bytes": 64 * MIB,
    "staging_bytes": 65 * MIB,
    "rows_per_file": 10000,
    "product_rows": 100000,
    "price_rows": 200000,
    "request_seconds": 15,
    "total_seconds": 180,
    "spacing_seconds": 1,
    "publication_spacing_seconds": 86400,
    "build_bytes": 1024,
    "metadata_bytes": 65536,
}


def _aware(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (TypeError, AttributeError, ValueError):
        raise CaptureRefused("aware_timestamp_required") from None


def batch_steps(groups, include_groups=False):
    steps = [{"filename": "build-before.txt", "url": STEPS[0][1], "kind": "text", "group_id": None}]
    if include_groups:
        steps.append({"filename": "groups.json", "url": STEPS[1][1], "kind": "groups", "group_id": None})
    for group in groups:
        group_id = group["group_id"]
        for kind in ("products", "prices"):
            steps.append(
                {
                    "filename": f"groups/{group_id}/{kind}.json",
                    "url": f"https://tcgcsv.com/tcgplayer/3/{group_id}/{kind}",
                    "kind": kind,
                    "group_id": group_id,
                }
            )
    steps.append({"filename": "build-after.txt", "url": STEPS[0][1], "kind": "text", "group_id": None})
    return steps


def make_batch_plan(
    root,
    groups,
    not_before,
    retained_groups_sha256,
    *,
    plan_id="hunt11-s1-first-batch-v1",
    include_groups=False,
    limits=None,
    purpose=None,
    refresh_cadence=None,
):
    plan = dict(
        schema="dex-tcgcsv-batch-plan-v1",
        plan_id=plan_id,
        root=str(Path(root).absolute()),
        not_before=not_before,
        groups=groups,
        include_groups=include_groups,
        retained_groups_sha256=retained_groups_sha256,
        limits=limits or dict(BATCH_LIMITS),
        steps=batch_steps(groups, include_groups),
        request_count=2 * len(groups) + 2 + int(include_groups),
    )
    # Omitted purpose preserves the exact legacy refresh plan and its digest.
    if purpose is not None:
        plan["purpose"] = purpose
    if refresh_cadence is not None:
        plan["refresh_cadence"] = refresh_cadence
    validate_batch_plan(plan, root)
    return plan


# One exhausted owner selection, code-bound to its proposal and partitions.
# Changing names or dates must never renew its consumed capacity.
R3_ACQUIRE1_PROPOSAL = "a5619a24eb41e7f677d8137121ed1d4a5d512af8f05f8b5ad4579311a23687cf"

R3_ACQUIRE1_GROUPS = (
    (630, 635, 1367, 1368, 1369, 1374, 1375, 1378, 1379, 1380, 1383, 1390, 1391, 1392, 1395, 1397),
    (1398, 1402, 1405, 1406, 1411, 1415, 1417, 1419, 1428, 1429, 1430, 1444, 1957, 2848, 2906, 3040),
    (3118, 3170, 17688, 22873, 23120, 23228, 23353, 23473, 23537, 23651, 23821, 24073, 24269, 24380),
)


def validate_batch_plan(plan, root):
    keys = {
        "schema",
        "plan_id",
        "root",
        "not_before",
        "groups",
        "include_groups",
        "retained_groups_sha256",
        "limits",
        "steps",
        "request_count",
    }
    if (
        not isinstance(plan, dict)
        or not keys <= set(plan) <= keys | {"purpose", "refresh_cadence", "timing_override"}
        or plan["schema"] != "dex-tcgcsv-batch-plan-v1"
        or "purpose" in plan
        and (not isinstance(plan["purpose"], str) or plan["purpose"] not in {"refresh", "initial_fill"})
    ):
        raise CaptureRefused("invalid_batch_plan")
    if "refresh_cadence" in plan and (
        not isinstance(plan["refresh_cadence"], str)
        or plan["refresh_cadence"]
        not in {"selected_groups", "selected_groups_new_build", "owner_r3_acquire1_same_build_once"}
        or plan.get("purpose", "refresh") != "refresh"
        or plan["include_groups"] is not False
    ):
        raise CaptureRefused("invalid_refresh_cadence")
    newer_build_override = plan.get("refresh_cadence") in {
        "selected_groups_new_build",
        "owner_r3_acquire1_same_build_once",
    }
    if (
        newer_build_override != ("timing_override" in plan)
        or newer_build_override
        and (
            not isinstance(plan["timing_override"], str)
            or not re.fullmatch(r"[a-z][a-z0-9-]{1,79}", plan["timing_override"])
        )
    ):
        raise CaptureRefused("invalid_timing_override")
    if (
        not isinstance(plan["plan_id"], str)
        or not re.fullmatch(r"[a-z][a-z0-9-]{1,79}", plan["plan_id"])
        or plan["root"] != str(Path(root).absolute())
        or type(plan["include_groups"]) is not bool
        or not isinstance(plan["retained_groups_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", plan["retained_groups_sha256"])
    ):
        raise CaptureRefused("invalid_batch_identity")
    _aware(plan["not_before"])
    groups = plan["groups"]
    if not isinstance(groups, list) or not 1 <= len(groups) <= 68:
        raise CaptureRefused("invalid_batch_groups")
    seen = set()
    for group in groups:
        if (
            not isinstance(group, dict)
            or set(group) != {"group_id", "name"}
            or type(group["group_id"]) is not int
            or not 0 < group["group_id"] <= 2147483647
            or group["group_id"] in seen
            or not isinstance(group["name"], str)
            or not group["name"].strip()
            or len(group["name"]) > 2000
        ):
            raise CaptureRefused("invalid_batch_groups")
        seen.add(group["group_id"])
    if plan.get("refresh_cadence") == "owner_r3_acquire1_same_build_once":
        partitions = {
            f"r3-acquire1-{R3_ACQUIRE1_PROPOSAL[:16]}-batch-{i}": gids
            for i, gids in enumerate(R3_ACQUIRE1_GROUPS, 1)
        }
        if tuple(g["group_id"] for g in groups) != partitions.get(plan["timing_override"]):
            raise CaptureRefused("r3_exception_exact_selection_required")
    limits = plan["limits"]
    if not isinstance(limits, dict) or set(limits) != set(BATCH_LIMITS):
        raise CaptureRefused("invalid_batch_limits")
    for key, maximum in BATCH_LIMITS.items():
        value = limits[key]
        if type(value) not in (int, float) or not 0 < value < float("inf"):
            raise CaptureRefused("invalid_batch_limits")
        if (
            key in {"spacing_seconds", "publication_spacing_seconds"}
            and value < maximum
            or key not in {"spacing_seconds", "publication_spacing_seconds"}
            and value > maximum
        ):
            raise CaptureRefused("batch_limit_expansion")
        if not key.endswith("seconds") and type(value) is not int:
            raise CaptureRefused("invalid_batch_limits")
    steps = batch_steps(groups, plan["include_groups"])
    if (
        plan["steps"] != steps
        or type(plan["request_count"]) is not int
        or plan["request_count"] != len(steps)
    ):
        raise CaptureRefused("batch_step_mismatch")
    return hashlib.sha256(_json_bytes(plan)).hexdigest()
