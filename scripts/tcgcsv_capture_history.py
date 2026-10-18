"""Read-only snapshot consumption history and conservative resource reservations.

The capture orchestrator holds the installation lock while consulting these
readers. Unknown or incomplete history cannot create new request capacity.
"""

import json
import os

from scripts.tcgcsv_capture_contract import MIB, CaptureRefused, _aware, _nonfinite, _unique_object


def _read_private_json(path, ceiling=8 * MIB):
    if path.is_symlink() or path.resolve(strict=True) != path:
        raise CaptureRefused("unsafe_accounting_file")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > ceiling:
            raise CaptureRefused("unsafe_accounting_file")
        body = stream.read(ceiling + 1)
    if len(body) > ceiling:
        raise CaptureRefused("accounting_capacity_exhausted")
    try:
        return json.loads(body, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    except (UnicodeError, ValueError, RecursionError):
        raise CaptureRefused("invalid_accounting") from None


def _history(accounting, metadata_ledger, *, group_history=None, resource_history=None):
    if not (accounting / "hunt11-five-request-v1.jsonl").is_file() or not metadata_ledger.is_file():
        raise CaptureRefused("historical_accounting_required")
    times, builds = [], []
    used_groups, unknown_groups, detailed_reservations = set(), False, set()
    group_times, group_builds = {}, {}
    files = sorted(accounting.glob("*.jsonl"))
    if len(files) > 1000:
        raise CaptureRefused("accounting_capacity_exhausted")
    for path in files:
        if (
            path.is_symlink()
            or path.stat().st_mode & 0o077
            or path.stat().st_nlink != 1
            or path.stat().st_size > 8 * MIB
        ):
            raise CaptureRefused("unsafe_accounting_file")
        try:
            lines = path.read_bytes().splitlines()
            if len(lines) > 10000:
                raise CaptureRefused("accounting_capacity_exhausted")
            consumed, closed, maximum = 0, False, None
            received_builds = []
            declared_groups, observed_groups, unknown_scope = None, set(), False
            reserved_at, consumed_times, observed_times = None, [], {}
            for index, line in enumerate(lines):
                row = json.loads(line, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
                if not isinstance(row, dict) or closed:
                    raise ValueError
                stage = row.get("stage")
                if index == 0:
                    maximum = row.get("maximum_attempts")
                    if stage != "selected" or type(maximum) is not int or not 1 <= maximum <= 139:
                        raise ValueError
                    if "group_ids" in row:
                        reserved_at = _aware(row.get("at"))
                        declared_groups = row["group_ids"]
                        if (
                            not isinstance(declared_groups, list)
                            or not 1 <= len(declared_groups) <= 68
                            or any(
                                type(gid) is not int or not 0 < gid <= 2147483647 for gid in declared_groups
                            )
                            or len(set(declared_groups)) != len(declared_groups)
                        ):
                            raise ValueError
                    if "purpose" in row and (
                        not isinstance(row["purpose"], str)
                        or row["purpose"] not in {"refresh", "initial_fill"}
                    ):
                        raise ValueError
                elif stage == "consumed":
                    consumed += 1
                    if (
                        type(row.get("attempt")) is not int
                        or row["attempt"] != consumed
                        or consumed > maximum
                    ):
                        raise ValueError
                    consumed_at = _aware(row["at"])
                    times.append(consumed_at)
                    consumed_times.append(consumed_at)
                    if path.name != "hunt11-five-request-v1.jsonl":
                        endpoint, group_id = row.get("endpoint"), row.get("group_id")
                        if endpoint in {"products", "prices"}:
                            if type(group_id) is not int or not 0 < group_id <= 2147483647:
                                unknown_scope = True
                            else:
                                observed_groups.add(group_id)
                                observed_times[group_id] = max(
                                    observed_times.get(group_id, consumed_at), consumed_at
                                )
                        elif endpoint not in {"text", "groups"} or group_id is not None:
                            unknown_scope = True
                elif stage in {"response", "received"}:
                    if not consumed or type(row.get("attempt")) is not int or row["attempt"] != consumed:
                        raise ValueError
                    if stage == "received" and row.get("publisher_built_at"):
                        received_builds.append(_aware(row["publisher_built_at"]))
                elif stage == "closed":
                    if (
                        type(row.get("consumed")) is not int
                        or row["consumed"] != consumed
                        or row.get("status") not in {"captured", "stopped"}
                        or row["status"] == "captured"
                        and consumed != maximum
                    ):
                        raise ValueError
                    closed = True
                else:
                    raise ValueError
            if not lines:
                raise ValueError
            if path.name == "hunt11-five-request-v1.jsonl":
                if (
                    maximum != 5
                    or consumed != 5
                    or not closed
                    or row["status"] != "captured"
                    or len(received_builds) != 2
                    or received_builds[0] != received_builds[1]
                ):
                    raise ValueError
            if consumed or declared_groups is not None:
                if path.name == "hunt11-five-request-v1.jsonl":
                    # Its immutable five-step implementation binds both data requests to 3170.
                    used_groups.add(3170)
                    group_times[3170] = max(group_times.get(3170, min(consumed_times)), *consumed_times)
                else:
                    if declared_groups is not None:
                        used_groups.update(declared_groups)
                        if not observed_groups <= set(declared_groups):
                            raise ValueError
                        # A failed first build still reserves every selected group.
                        # Actual data attempts, including uncertain ones, can only
                        # advance that group's daily reservation.
                        for gid in declared_groups:
                            group_times[gid] = max(
                                group_times.get(gid, reserved_at),
                                reserved_at,
                                observed_times.get(gid, reserved_at),
                            )
                    else:
                        used_groups.update(observed_groups)
                        unknown_scope = unknown_scope or not observed_groups
                        for gid, at in observed_times.items():
                            group_times[gid] = max(group_times.get(gid, at), at)
                    unknown_groups = unknown_groups or unknown_scope
                if path.name.startswith("batch-"):
                    detailed_reservations.add("tcgcsv-" + path.stem)
            builds.extend(received_builds)
            # Build checks cover the full reserved scope, even when no product
            # request followed. Preserve the global result for legacy plans.
            scoped_groups = (
                {3170}
                if path.name == "hunt11-five-request-v1.jsonl"
                else (set(declared_groups) if declared_groups is not None else observed_groups)
            )
            if received_builds:
                for gid in scoped_groups:
                    group_builds[gid] = max(group_builds.get(gid, min(received_builds)), *received_builds)
        except (KeyError, UnicodeError, ValueError, RecursionError):
            raise CaptureRefused("invalid_accounting") from None
    metadata = {"schema": "dex-tcgcsv-metadata-attempts-v1", "attempts": []}
    if metadata_ledger.exists():
        metadata = _read_private_json(metadata_ledger, MIB)
        if (
            not isinstance(metadata, dict)
            or set(metadata) != {"schema", "attempts"}
            or metadata["schema"] != "dex-tcgcsv-metadata-attempts-v1"
            or not isinstance(metadata["attempts"], list)
            or len(metadata["attempts"]) > 999
        ):
            raise CaptureRefused("invalid_accounting")
        for row in metadata["attempts"]:
            if (
                not isinstance(row, dict)
                or set(row) != {"plan", "manifest_sha256", "reserved_at", "status"}
                or row["status"] not in {"consumed", "complete", "stopped", "timeout", "failed"}
            ):
                raise CaptureRefused("invalid_accounting")
            times.append(_aware(row["reserved_at"]))
            if row["plan"] != "tcgcsv-pokemon-groups-first-v1" and row["plan"] not in detailed_reservations:
                # The documented historical metadata operator sends only the groups route.
                # Other incomplete reservations need their detailed durable group selection.
                unknown_groups = True
    if group_history is not None:
        group_history.update(groups=used_groups, unknown=unknown_groups)
    if resource_history is not None:
        resource_history.update(
            latest_by_group=group_times, builds_by_group=group_builds, unknown=unknown_groups
        )
    return max(times, default=None), max(builds, default=None), metadata
