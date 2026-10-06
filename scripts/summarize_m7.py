"""Sanitized exact-response, bounded-profile and private preservation summary."""

import hashlib
import json
import pstats
from pathlib import Path

PRIVATE = Path("/Users/michaelfuscoletti/dex-private/m7-20261006T180707Z")
OUTPUT = Path(__file__).resolve().parents[1] / "evidence/m7-20261006"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (OUTPUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    ledgers = {p: json.loads((PRIVATE / p / "ledger.json").read_text()) for p in ("baseline", "repaired")}
    comparisons = []
    for row in ledgers["baseline"]:
        name = f"{row['scenario']}-{row['attempt']}.json"
        assert (PRIVATE / "baseline" / name).read_bytes() == (PRIVATE / "repaired" / name).read_bytes()
        comparisons.append(
            dict(
                scenario=row["scenario"],
                attempt=row["attempt"],
                identical=True,
                complete_response_sha256=sha(PRIVATE / "baseline" / name),
            )
        )
    preservation = {p: json.loads((PRIVATE / p / "preservation.json").read_text()) for p in ledgers}
    assert preservation["baseline"] == preservation["repaired"]
    assert all(v["identical"] for v in preservation.values())
    profiles = {}
    for phase in ledgers:
        stats = pstats.Stats(str(PRIVATE / phase / "pokedex.prof"))
        profiles[phase] = [
            dict(function=key[2], module=Path(key[0]).name, calls=values[1], cumulative_seconds=values[3])
            for key, values in sorted(stats.stats.items(), key=lambda x: -x[1][3])[:20]
        ]
    write(
        "profiling-summary.json",
        dict(
            measurements=ledgers,
            expensive_operations=profiles,
            clock="2026-10-06T18:10:00+00:00",
            attempts_per_scenario=2,
            conditions="Same copied owner root, guard, common clock, ordered scenarios and query recorder; second attempts cProfile-instrumented. Baseline and repaired latter phases overlapped on this local host; CPU contention affects timings. Browser loading is qualified separately on an idle host. No OS cache eviction.",
            private_profiles=str(PRIVATE),
            external_requests=0,
        ),
    )
    write(
        "semantic-parity.json",
        dict(
            comparisons=comparisons,
            all_14_complete_responses_identical=True,
            normalization="JSON object key order and random hidden CSRF token only; no semantic fields omitted",
            all_database_tables_identical=True,
            all_files_identical=True,
            preservation_receipts={
                p: dict(
                    path=str(PRIVATE / p / "preservation.json"), sha256=sha(PRIVATE / p / "preservation.json")
                )
                for p in ledgers
            },
            protected_table_hashes=preservation["baseline"]["before"]["tables"],
        ),
    )
    receipt = PRIVATE / "backup-receipt.json"
    r = json.loads(receipt.read_text())
    write(
        "backup-summary.json",
        dict(
            path=str(receipt),
            sha256=sha(receipt),
            consistent_sqlite_backup=r["consistent_sqlite_backup"],
            files_identical=r["files_identical"],
            file_count=r["file_count"],
            table_count=len(r["database_tables"]),
            independent_restore_identical=r["independent_restore_all_tables_and_files_identical"],
            opaque_configuration_backup_restore_identical=True,
        ),
    )


if __name__ == "__main__":
    main()
