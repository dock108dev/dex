"""Bounded read-only Actions metadata acquisition; no analysis, writes or notifications."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta
from typing import Any

from scripts.ci.report_readers import ReportError


def gh_api(repository: str, suffix: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    command = ["gh", "api", "--method", "GET", f"repos/{repository}/{suffix}"]
    for key, value in (fields or {}).items():
        command.extend(["-f", f"{key}={value}"])
    try:
        response = subprocess.run(command, capture_output=True, text=True, timeout=25, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReportError("Read-only GitHub API unavailable or timed out") from exc
    if response.returncode:
        # Do not retain arbitrary authentication/CLI output in report artifacts.
        raise ReportError(f"Read-only GitHub API failed (exit {response.returncode})")
    try:
        data = json.loads(response.stdout)
    except json.JSONDecodeError as exc:
        raise ReportError("Malformed GitHub API JSON") from exc
    if not isinstance(data, dict):
        raise ReportError("GitHub API response must be an object")
    return data


def repository_resources(repository: str, *, api=gh_api) -> dict[str, Any]:
    """Two bounded metadata reads; artifact page subtotal is never total retained storage."""
    result: dict[str, Any] = {"artifacts": None, "cache": None, "errors": []}
    for kind, endpoint in (("artifacts", "actions/artifacts"), ("cache", "actions/cache/usage")):
        try:
            data = api(repository, endpoint, {"per_page": "100"} if kind == "artifacts" else None)
            if kind == "artifacts":
                artifacts, total = data.get("artifacts"), data.get("total_count")
                if not isinstance(artifacts, list) or len(artifacts) > 100:
                    raise ReportError("Malformed bounded artifact metadata")
                if type(total) is not int or total < len(artifacts):
                    raise ReportError("Invalid artifact total")
                active = []
                for item in artifacts:
                    if not isinstance(item, dict) or type(item.get("expired")) is not bool:
                        raise ReportError("Invalid artifact expiry metadata")
                    size = item.get("size_in_bytes")
                    if type(size) is not int or size < 0:
                        raise ReportError("Invalid artifact size")
                    if not item["expired"]:
                        active.append(size)
                result[kind] = {
                    "total_count": total,
                    "returned_count": len(artifacts),
                    "page_limit": 100,
                    "active_bytes_subtotal": sum(active),
                    "complete_listing": total == len(artifacts),
                    "total_active_bytes": sum(active) if total == len(artifacts) else None,
                }
            else:
                count, size = data.get("active_caches_count"), data.get("active_caches_size_in_bytes")
                if any(type(value) is not int or value < 0 for value in (count, size)):
                    raise ReportError("Invalid cache usage metadata")
                result[kind] = {"active_count": count, "active_bytes": size}
        except ReportError as error:
            result["errors"].append(f"{kind}: {error}")
    result["scope"] = "repository metadata at collection time; no downloads, billing or per-run allocation"
    return result


def load_live(repository: str, now: datetime, limit: int, *, api=gh_api) -> tuple[dict[str, Any], list[str]]:
    since = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = api(
        repository, "actions/runs", {"status": "completed", "per_page": str(limit), "created": f">={since}"}
    )
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise ReportError("GitHub run response must contain workflow_runs")
    errors = []
    for run in runs[:limit]:
        if not isinstance(run, dict) or not isinstance(run.get("id"), int):
            raise ReportError("Malformed workflow run identity")
        attempt = run.get("run_attempt")
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
            raise ReportError("Malformed workflow run attempt")
        try:
            run["jobs_snapshot"] = api(
                repository, f"actions/runs/{run['id']}/attempts/{attempt}/jobs", {"per_page": "100"}
            )
        except ReportError as exc:
            errors.append(f"Run {run['id']} timestamps unavailable: {exc}")
        if attempt > 1:
            try:
                run["first_attempt"] = api(repository, f"actions/runs/{run['id']}/attempts/1")
            except ReportError as exc:
                errors.append(f"Run {run['id']} first attempt unavailable: {exc}")
    payload["workflow_runs"] = runs[:limit]
    return payload, errors
