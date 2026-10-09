#!/usr/bin/env python3
"""Read at most 30 recent completed Actions runs; never post comments or alter settings."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from .report import ReportError, identity, link, markdown, read_json, write_result
except ImportError:  # Direct script invocation in Actions.
    from report import ReportError, identity, link, markdown, read_json, write_result

REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
CONCLUSIONS = {
    "success",
    "failure",
    "cancelled",
    "neutral",
    "skipped",
    "stale",
    "timed_out",
    "action_required",
    "startup_failure",
}
ELIGIBLE = {"success", "failure", "timed_out", "action_required", "startup_failure"}


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(UTC) if result.tzinfo is not None else None


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


def load_live(repository: str, now: datetime, limit: int) -> tuple[dict[str, Any], list[str]]:
    since = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = gh_api(
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
            run["jobs_snapshot"] = gh_api(
                repository, f"actions/runs/{run['id']}/attempts/{attempt}/jobs", {"per_page": "100"}
            )
        except ReportError as exc:
            errors.append(f"Run {run['id']} timestamps unavailable: {exc}")
        if attempt > 1:
            try:
                run["first_attempt"] = gh_api(repository, f"actions/runs/{run['id']}/attempts/1")
            except ReportError as exc:
                errors.append(f"Run {run['id']} first attempt unavailable: {exc}")
    payload["workflow_runs"] = runs[:limit]
    return payload, errors


def duration(run: dict[str, Any]) -> tuple[float | None, str | None]:
    start = timestamp(run.get("run_started_at"))
    # Explicit complete timestamps are supported in retained fixture exports. REST updated_at is never substituted.
    complete = timestamp(run.get("completed_at"))
    if start and complete and complete >= start:
        return (complete - start).total_seconds(), "run_started_at to explicit completed_at"
    snapshot = run.get("jobs_snapshot")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("jobs"), list):
        return None, None
    jobs = snapshot["jobs"]
    total = snapshot.get("total_count")
    if not start or not jobs or not isinstance(total, int) or isinstance(total, bool) or total != len(jobs):
        return None, None
    completed = [timestamp(job.get("completed_at")) if isinstance(job, dict) else None for job in jobs]
    if any(value is None for value in completed):
        return None, None
    end = max(completed)
    if end < start:
        return None, None
    return (
        end - start
    ).total_seconds(), "run_started_at to latest completed_at of all attempt jobs (observed span)"


def resource_observation(run: dict[str, Any]) -> tuple[float | None, int | None, str | None]:
    """Observed execution time sums parallel jobs; it is not elapsed or billed time."""
    snapshot = run.get("jobs_snapshot")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("jobs"), list):
        return None, None, "jobs snapshot unavailable"
    jobs, total = snapshot["jobs"], snapshot.get("total_count")
    if isinstance(total, bool) or not isinstance(total, int) or total != len(jobs):
        return None, None, "jobs snapshot incomplete or paginated"
    seconds, observed_jobs = 0.0, 0
    for job in jobs:
        if (
            not isinstance(job, dict)
            or job.get("conclusion") not in CONCLUSIONS
            or job.get("status", "completed") != "completed"
        ):
            return None, None, "job conclusion incomplete or unavailable"
        if job["conclusion"] == "skipped" or (
            job["conclusion"] == "cancelled" and job.get("started_at") is None
        ):
            continue
        start, complete = timestamp(job.get("started_at")), timestamp(job.get("completed_at"))
        if start is None or complete is None or complete < start:
            return None, None, "executed job timestamps missing or inconsistent"
        seconds += (complete - start).total_seconds()
        observed_jobs += 1
    return round(seconds / 60, 6), observed_jobs, None


def start_delay(run: dict[str, Any]) -> float | None:
    """First-attempt creation-to-logical-run-start proxy; API does not expose exact queue time."""
    if run.get("run_attempt") != 1:
        return None  # A rerun retains the original created_at, so the proxy is not comparable.
    created, start = timestamp(run.get("created_at")), timestamp(run.get("run_started_at"))
    return (start - created).total_seconds() if created and start and start >= created else None


def percentile95(values: list[float]) -> float | None:
    # Nearest rank; p95 is intentionally unavailable for fewer than 20 observations.
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if len(values) >= 20 else None


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    conclusions = {value: sum(run["conclusion"] == value for run in runs) for value in sorted(CONCLUSIONS)}
    first = [run if run["run_attempt"] == 1 else run.get("first_attempt") for run in runs]
    first_conclusions = [
        attempt.get("conclusion") if isinstance(attempt, dict) else None for attempt in first
    ]
    eligible = [value for value in first_conclusions if value in ELIGIBLE]
    reruns = [run for run in runs if run["run_attempt"] > 1]
    recovered = sum(
        run["conclusion"] == "success" and first_conclusion in ELIGIBLE - {"success"}
        for run, first_conclusion in zip(runs, first_conclusions, strict=True)
    )
    measured = [
        (run["observed_duration_seconds"], run["duration_method"])
        for run in runs
        if run["observed_duration_seconds"] is not None and run["conclusion"] != "cancelled"
    ]
    methods = sorted({method for _, method in measured})
    # Do not silently compare distinct timestamp methods; produce separate distributions.
    speed = []
    for method in methods:
        values = [value for value, value_method in measured if value_method == method]
        speed.append(
            {
                "method": method,
                "sample_size": len(values),
                "unit": "seconds",
                "median": statistics.median(values) if len(values) >= 5 else None,
                "p95": percentile95(values),
                "baseline": None,
                "delta": None,
            }
        )
    resources = [run["observed_runner_minutes"] for run in runs if run["observed_runner_minutes"] is not None]
    delays = [
        run["creation_to_run_start_seconds"]
        for run in runs
        if run["creation_to_run_start_seconds"] is not None
    ]
    return {
        "sample_size": len(runs),
        "latest_conclusions": conclusions,
        "first_attempt_known": sum(value in CONCLUSIONS for value in first_conclusions),
        "first_attempt_missing": sum(value not in CONCLUSIONS for value in first_conclusions),
        "first_attempt_cancelled": sum(value == "cancelled" for value in first_conclusions),
        "first_attempt_eligible": len(eligible),
        "first_attempt_pass_percent": round(100 * eligible.count("success") / len(eligible), 2)
        if eligible
        else None,
        "rerun_runs": len(reruns),
        "rerun_attempts": sum(run["run_attempt"] - 1 for run in reruns),
        "recovered_after_failure": recovered,
        "suspected_flakes": None,
        "failure_categories": conclusions,
        "observed_duration": speed,
        "queue_seconds": None,
        "critical_path_seconds": None,
        "runner_minutes": sum(resources) if resources and len(resources) == len(runs) else None,
        "observed_runner_minutes": {
            "sample_size": len(resources),
            "unavailable_runs": len(runs) - len(resources),
            "measured_subtotal": round(sum(resources), 6) if resources else None,
            "unit": "minutes",
            "method": "sum completed_at minus started_at for executed jobs in complete attempt snapshots; "
            "skipped and cancelled-before-start jobs excluded; cancelled-after-start jobs included; no billing factors",
        },
        "creation_to_run_start_delay": {
            "sample_size": len(delays),
            "unavailable_or_rerun_runs": len(runs) - len(delays),
            "unit": "seconds",
            "median": statistics.median(delays) if len(delays) >= 5 else None,
            "p95": percentile95(delays),
            "method": "created_at to run_started_at for first attempts only; observed delay proxy, not exact runner queue",
        },
        "artifact_bytes": None,
        "cache_bytes": None,
        "billing_cost": None,
    }


def analyze(payload: Any, now: datetime, primary_branch: str, limit: int) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
        raise ReportError("Health snapshot must contain workflow_runs array")
    window_start = now - timedelta(days=30)
    candidates = []
    excluded = 0
    for raw in payload["workflow_runs"]:
        if not isinstance(raw, dict):
            raise ReportError("Malformed workflow run")
        created = timestamp(raw.get("created_at"))
        if created is None:
            raise ReportError("Workflow run created_at missing or malformed")
        if raw.get("status") != "completed" or not window_start <= created <= now:
            excluded += 1
            continue
        if raw.get("conclusion") not in CONCLUSIONS:
            raise ReportError("Completed workflow run has missing or invalid conclusion")
        attempt = raw.get("run_attempt")
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
            raise ReportError("Workflow run attempt missing or malformed")
        measured, method = duration(raw)
        runner_minutes, runner_jobs, resource_reason = resource_observation(raw)
        candidates.append(
            {
                "id": raw.get("id"),
                "workflow_id": raw.get("workflow_id"),
                "workflow_path": raw.get("path"),
                "name": raw.get("name"),
                "head_sha": raw.get("head_sha"),
                "head_branch": raw.get("head_branch"),
                "event": raw.get("event"),
                "html_url": raw.get("html_url"),
                "created_at": created.isoformat(),
                "conclusion": raw["conclusion"],
                "run_attempt": attempt,
                "first_attempt": (
                    {"conclusion": raw["first_attempt"].get("conclusion")}
                    if isinstance(raw.get("first_attempt"), dict)
                    else None
                ),
                "observed_duration_seconds": measured,
                "duration_method": method,
                "observed_runner_minutes": runner_minutes,
                "observed_runner_job_count": runner_jobs,
                "resource_unavailable_reason": resource_reason,
                "creation_to_run_start_seconds": start_delay(raw),
            }
        )
    runs = sorted(candidates, key=lambda run: run["created_at"], reverse=True)[:limit]
    group_runs = {
        "pull_request": [run for run in runs if run["event"] == "pull_request"],
        "primary_branch": [
            run for run in runs if run["event"] == "push" and run["head_branch"] == primary_branch
        ],
        "other": [
            run
            for run in runs
            if run["event"] != "pull_request"
            and not (run["event"] == "push" and run["head_branch"] == primary_branch)
        ],
    }
    groups = {}
    for name, group in group_runs.items():

        def workflow_key(run: dict[str, Any]) -> str:
            if run["workflow_id"] is not None:
                return str(run["workflow_id"])
            if isinstance(run["workflow_path"], str) and run["workflow_path"]:
                return run["workflow_path"]
            return f"unavailable identity (run {run['id']})"

        workflows = sorted({workflow_key(run) for run in group})
        aggregate = summarize(group)
        if len(workflows) > 1:
            for metric in (
                "observed_duration",
                "runner_minutes",
                "observed_runner_minutes",
                "creation_to_run_start_delay",
            ):
                aggregate[metric] = None
            aggregate["measurement_scope_reason"] = (
                "multiple workflow identities; inspect comparable by_workflow measurements"
            )
        groups[name] = {
            "aggregate": aggregate,
            "by_workflow": {
                workflow: summarize([run for run in group if workflow_key(run) == workflow])
                for workflow in workflows
            },
        }
    return {
        "schema_version": 1,
        "kind": "ci-health",
        "status": "AVAILABLE",
        "recorded_at": now.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": now.isoformat(),
        "primary_branch": primary_branch,
        "limit": limit,
        "sample_size": len(runs),
        "excluded_incomplete_or_outside_window": excluded,
        "method": "latest completed runs created within 30 days; no pagination; conclusions per latest attempt",
        "duration_policy": "cancelled runs excluded; median requires 5 samples; nearest-rank p95 requires 20; methods separated",
        "first_attempt_policy": "cancelled, skipped, neutral, stale and unavailable first attempts excluded from pass-rate denominator",
        "flake_policy": "A recovered rerun does not establish flakiness; no test-level historical evidence collected",
        "unavailable_metrics": {
            "exact_queue": "API logical run start does not identify runner queue eligibility or runner assignment",
            "critical_path": "job timestamps do not establish the complete dependency graph or runner wait edges",
            "quota_and_billing": "billing/quota endpoints and billing factors are outside this read-only run sample",
            "artifact_and_cache_sizes": "no artifact/cache metadata endpoints queried by this bounded collector",
        },
        "groups": groups,
        "runs": runs,
        "baseline": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--primary-branch", default="main")
    parser.add_argument("--limit", type=int, default=30, choices=range(1, 31))
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--now", help="Explicit ISO timestamp for reproducible fixture validation")
    args = parser.parse_args(argv)
    now = timestamp(args.now) if args.now else datetime.now(UTC)
    if now is None:
        parser.error("--now must include a valid timezone")
    errors = []
    try:
        if args.snapshot:
            payload = read_json(args.snapshot)
            source = "local retained snapshot"
        else:
            if not args.repository or not REPOSITORY.fullmatch(args.repository):
                raise ReportError("A valid owner/repository is required for read-only GitHub sampling")
            payload, errors = load_live(args.repository, now, args.limit)
            source = "read-only GitHub Actions REST API"
        record = analyze(payload, now, args.primary_branch, args.limit)
        record.update({"source": source, "repository": args.repository, "errors": errors})
        record["identity"] = identity()
        record["environment"] = {
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        }
        summary = [
            "### CI health: bounded completed-run sample",
            "",
            f"Sample: {record['sample_size']} runs; {markdown(record['window_start'])} to {markdown(record['window_end'])}; "
            f"maximum {args.limit} runs. Source: {markdown(source)}.",
            "",
            "| Scope | Runs | First-attempt pass / eligible | Cancelled latest | Rerun runs / recovered |",
            "|---|---|---|---|---|",
        ]
        summary[2:2] = [
            f"Collection SHA: {markdown(record['identity']['tested_sha'] or 'unavailable')}; "
            f"ref: {markdown(record['identity']['ref'] or 'unavailable')}; "
            f"event: {markdown(record['identity']['event'] or 'unavailable')}; "
            f"runtime: Python {markdown(record['environment']['python'])}, "
            f"{markdown(record['environment']['os'])}/{markdown(record['environment']['architecture'])}.",
            "Run: "
            + (
                link("Actions run", record["identity"]["run_url"])
                if record["identity"]["run_url"]
                else "unavailable"
            ),
            "",
        ]
        for scope, group in record["groups"].items():
            metrics = group["aggregate"]
            rate = metrics["first_attempt_pass_percent"]
            summary += [
                f"| {markdown(scope)} | {metrics['sample_size']} | "
                f"{str(rate) + '%' if rate is not None else 'unavailable'} / {metrics['first_attempt_eligible']} | "
                f"{metrics['latest_conclusions']['cancelled']} | {metrics['rerun_runs']} / {metrics['recovered_after_failure']} |"
            ]
        summary += [
            "",
            "First-attempt pass rate excludes cancelled, skipped, neutral, stale and unavailable attempts. "
            "Recovered reruns do not establish flakes. Full metrics separate workflow identity and PR/primary-branch evidence.",
            "",
            "Speed by comparable timestamp method (cancelled runs excluded):",
        ]
        for scope, group in record["groups"].items():
            for workflow, metrics in group["by_workflow"].items():
                for speed in metrics["observed_duration"]:
                    summary += [
                        f"- {markdown(scope)}, workflow {markdown(workflow)}: n={speed['sample_size']}; "
                        f"median {speed['median'] if speed['median'] is not None else 'unavailable'} seconds; "
                        f"p95 {speed['p95'] if speed['p95'] is not None else 'unavailable'} seconds. "
                        f"Method: {markdown(speed['method'])}."
                    ]
        summary += [
            "",
            "Observed resources and start delay by scope/workflow (include cancelled attempts when timestamps support them):",
        ]
        for scope, group in record["groups"].items():
            for workflow, metrics in group["by_workflow"].items():
                resource, delay = metrics["observed_runner_minutes"], metrics["creation_to_run_start_delay"]
                summary += [
                    f"- {markdown(scope)}, workflow {markdown(workflow)}: observed job-time subtotal "
                    f"{resource['measured_subtotal'] if resource['measured_subtotal'] is not None else 'unavailable'} minutes "
                    f"across {resource['sample_size']}/{metrics['sample_size']} complete snapshots; "
                    f"{resource['unavailable_runs']} unavailable. "
                    f"Creation-to-run-start delay proxy n={delay['sample_size']}; "
                    f"median {delay['median'] if delay['median'] is not None else 'unavailable'} seconds; "
                    f"p95 {delay['p95'] if delay['p95'] is not None else 'unavailable'} seconds."
                ]
        summary += [
            "Median requires 5 observations; nearest-rank p95 requires 20. REST updated_at is not a completion timestamp. "
            "Job minutes sum execution spans across parallel jobs, exclude skipped/cancelled-before-start jobs, and do not "
            "represent elapsed run time or billed minutes. The delay proxy uses first-attempt created_at to run_started_at; "
            "it is not exact queue time. Exact queue, critical path, quota/billing, cache/artifact sizes and trend deltas "
            "remain unavailable; reasons are retained in the metrics record."
        ]
        summary += [f"- Sampling limitation: {markdown(error)}" for error in errors[:10]]
        summary += [
            "",
            "Next action: inspect the retained per-workflow sample and exact current candidate gates; "
            "historical results do not qualify a changed candidate.",
        ]
        write_result(args.output, record, "\n".join(summary))
        return 0
    except ReportError as exc:
        record = {
            "schema_version": 1,
            "kind": "ci-health",
            "status": "UNAVAILABLE",
            "recorded_at": now.isoformat(),
            "repository": args.repository,
            "sample_size": None,
            "errors": [str(exc)],
            "groups": None,
            "identity": identity(),
        }
        write_result(
            args.output,
            record,
            f"### CI health: UNAVAILABLE\n\n{markdown(exc)}. "
            "No historical pass rate, speed or flake claim is available.",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
