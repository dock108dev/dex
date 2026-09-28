"""Bounded, explicit local photo evaluation; never touches the collection or API budget.

Manifest: [{"id":"front-1","image":"/absolute/photo.jpg",
            "expected":{"name":"Pikachu","number":"58","set_name":"Base Set"}}]
Labels must be established before running. Keep manifest, photos and output private.
"""

import argparse
import json
import os
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile

from pokemon_hunter.beta import codex_recognition, scans


def outcome(clues, expected):
    fields = ("name", "number", "set_name")
    if clues.status != "readable" or any(getattr(clues, k) is None for k in fields):
        return "unresolved"
    return (
        "correct" if all(getattr(clues, k).casefold() == expected[k].casefold() for k in fields) else "wrong"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    entries = json.loads(args.manifest.read_text())
    if not isinstance(entries, list) or not 1 <= len(entries) <= 6:
        parser.error("Use one to six independently labeled card photos")
    for entry in entries:
        if not isinstance(entry.get("id"), str) or not all(
            isinstance(entry.get("expected", {}).get(k), str) and entry["expected"][k]
            for k in ("name", "number", "set_name")
        ):
            parser.error("Each photo needs an id and preassigned name, number and set_name labels")
    # Refuse overwrite so previous attempts and pre-correction results remain evidence.
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    results = []
    for entry in entries:
        image = Path(entry["image"])
        if not image.is_absolute() or image.stat().st_size > 8_000_000:
            parser.error("Use absolute image paths and photos no larger than 8 MB")
        normalized = scans.normalized(SimpleUploadedFile(image.name, image.read_bytes()))
        try:
            clues, usage = codex_recognition.recognize([normalized], args.output, job_id=entry["id"])
            result = {
                "id": entry["id"],
                "expected": entry["expected"],
                "clues": clues.model_dump(),
                "outcome": outcome(clues, entry["expected"]),
                "usage": usage,
            }
        except codex_recognition.RecognitionError as exc:
            result = {"id": entry["id"], "outcome": "unresolved", "error": str(exc)}
        attempt = json.loads((args.output / "codex-usage.jsonl").read_text().splitlines()[-1])
        result["latency"] = attempt["latency"]
        results.append(result)
        report = {
            "model": codex_recognition.MODEL,
            "metric": "visible identity before manual correction",
            "counts": {
                k: sum(r["outcome"] == k for r in results) for k in ("correct", "wrong", "unresolved")
            },
            "results": results,
        }
        fd = os.open(args.output / "results.json", os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(report, stream, indent=2)
    print(json.dumps(report["counts"]))


if __name__ == "__main__":
    main()
