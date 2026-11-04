"""Combine validated shard coverage per runtime, never across Python versions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from coverage import Coverage, CoverageData

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci.behavior_shards import SHARDS, modules
from scripts.ci.report import identity
from scripts.ci.report_readers import ReportError, read_job_metrics


def combine(root: Path, output: Path, runtime: str) -> dict:
    selected = {}
    for path in sorted(root.glob("*/ci/behavior/metrics.json")):
        record = read_job_metrics(path)
        if ".".join(record["environment"]["python"].split(".")[:2]) != runtime:
            continue
        shard = record["name"].removeprefix("Behavior: ")
        if shard not in SHARDS or shard in selected:
            raise ReportError("Unknown or duplicate behavior shard")
        if record["result"] != "PASS" or record["environment"]["os"] != "Linux":
            raise ReportError("Behavior shard did not pass on the required platform")
        for field, expected in identity().items():
            if expected and record["identity"].get(field) != expected:
                raise ReportError(f"Behavior shard {field} differs from this run")
        expected_suites = {"tests." + p.stem for p in modules(shard)}
        tests = record["reports"]["junit"]
        if (
            not tests
            or set(tests["expected_suites"]) != expected_suites
            or any(suite["executed"] == 0 for suite in tests["expected_suites"].values())
        ):
            raise ReportError("Behavior shard is missing required module execution")
        selected[shard] = path.parent
    if set(selected) != set(SHARDS):
        raise ReportError(f"Missing behavior shards for Python {runtime}")

    output.mkdir(parents=True, exist_ok=True)
    combined = Coverage(data_file=str(output / "coverage.data"))
    for directory in selected.values():
        source = directory / "coverage.data"
        if not source.is_file():
            raise ReportError("Missing shard coverage data")
        data = CoverageData(basename=str(source))
        data.read()
        if not data.has_arcs() or not data.measured_files():
            raise ReportError("Missing branch coverage in shard data")
        combined.get_data().update(data)
    combined.save()
    combined.json_report(outfile=str(output / "coverage.json"))
    combined.xml_report(outfile=str(output / "coverage.xml"))
    return {"python": runtime, "shards": list(selected), "result": "PASS"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", action="append", required=True)
    args = parser.parse_args()
    for runtime in args.python:
        result = combine(args.reports, args.output / f"py{runtime}", runtime)
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
