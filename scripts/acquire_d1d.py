"""One-shot authorized D1d acquisition. Existing ledger forbids rerunning this budget."""

import hashlib
import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/d1d-20261005"
RAW = Path("/Users/michaelfuscoletti/dex-private/d1d-20261005/source-evidence")
LIMIT = 10 * 1024 * 1024


def now():
    return datetime.now(UTC).isoformat()


def save(path, value):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(value, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def run():
    OUT.mkdir(exist_ok=True)
    ledgerpath = OUT / "attempt-ledger.json"
    # O_EXCL closes this budget against rerun, including after interruption.
    with ledgerpath.open("x") as f:
        f.write("{}\n")
        f.flush()
        os.fsync(f.fileno())
    RAW.mkdir(parents=True, mode=0o700)
    start = time.monotonic()
    ledger = dict(
        provider="tcgdex",
        language="en",
        set_id="det1",
        max_attempts=19,
        retries=0,
        per_attempt_seconds=15,
        total_seconds=300,
        retained_response_limit=LIMIT,
        started_at=now(),
        attempts=[],
        state="active",
    )
    save(ledgerpath, ledger)

    def request(key, url):
        remaining = 300 - (time.monotonic() - start)
        used = sum(a.get("response_bytes", 0) for a in ledger["attempts"])
        if remaining <= 0 or used >= LIMIT or len(ledger["attempts"]) >= 19:
            raise ValueError("Acquisition budget exhausted")
        body = RAW / (key + ".raw")
        headers = RAW / (key + ".headers")
        stderr = RAW / (key + ".transport.txt")
        row = dict(
            attempt=len(ledger["attempts"]) + 1,
            key=key,
            url=url,
            reserved_at=now(),
            invoked_at=None,
            outcome="reserved-consumed",
            response_path=str(body),
            headers_path=str(headers),
        )
        ledger["attempts"].append(row)
        save(ledgerpath, ledger)
        row["invoked_at"] = now()
        save(ledgerpath, ledger)
        try:
            result = subprocess.run(
                [
                    "curl",
                    "--silent",
                    "--show-error",
                    "--retry",
                    "0",
                    "--max-redirs",
                    "0",
                    "--max-time",
                    str(min(15, remaining)),
                    "--max-filesize",
                    str(LIMIT - used),
                    "--proto",
                    "=https",
                    "--dump-header",
                    str(headers),
                    "--output",
                    str(body),
                    "--write-out",
                    "%{http_code}",
                    url,
                ],
                capture_output=True,
                timeout=min(15, remaining) + 1,
            )
            row["transport_exit"] = result.returncode
            row["http_status"] = result.stdout.decode(errors="replace")
            stderr.write_bytes(result.stderr)
        except (subprocess.TimeoutExpired, OSError) as exc:
            row["transport_exit"] = None
            row["http_status"] = None
            stderr.write_text(type(exc).__name__ + ": invocation failed or exceeded deadline\n")
        row["transport_evidence_path"] = str(stderr)
        row["transport_sha256"] = hashlib.sha256(stderr.read_bytes()).hexdigest()
        row["finished_at"] = now()
        data = body.read_bytes() if body.exists() else b""
        row["response_bytes"] = len(data)
        row["response_sha256"] = hashlib.sha256(data).hexdigest() if body.exists() else None
        row["response_present"] = body.exists()
        row["outcome"] = "transport-failure" if row["transport_exit"] != 0 else "response-received"
        if headers.exists():
            row["headers_sha256"] = hashlib.sha256(headers.read_bytes()).hexdigest()
        save(ledgerpath, ledger)
        if row["transport_exit"] != 0:
            raise ValueError("Transport failure; any partial response is not usable source evidence")
        if row["http_status"] != "200":
            row["outcome"] = "http-denial" if row["http_status"] in {"401", "403", "429"} else "http-unusable"
            save(ledgerpath, ledger)
            raise ValueError("Unusable HTTP status: " + row["http_status"])
        if time.monotonic() - start > 300 or sum(a["response_bytes"] for a in ledger["attempts"]) > LIMIT:
            raise ValueError("Acquisition ceiling exceeded")
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValueError("Expected object")
        except (ValueError, UnicodeError) as exc:
            row["outcome"] = "unusable-response"
            save(ledgerpath, ledger)
            raise ValueError("Unusable JSON object") from exc
        row["outcome"] = "usable-json-pending-identity-review"
        save(ledgerpath, ledger)
        return parsed

    try:
        source = request("set", "https://api.tcgdex.net/v2/en/sets/det1")
        briefs = source.get("cards", [])
        if (
            source.get("id") != "det1"
            or source.get("name") != "Detective Pikachu"
            or source.get("language", "en") != "en"
            or len(briefs) != 18
            or source.get("cardCount", {}).get("total") != 18
        ):
            raise ValueError("Set identity/language/count mismatch")
        ids = [r["id"] for r in briefs]
        nums = [r["localId"] for r in briefs]
        if (
            len(set(ids)) != 18
            or len(set(nums)) != 18
            or any(not re.fullmatch(r"det1-[A-Za-z0-9]+", i) for i in ids)
        ):
            raise ValueError("Duplicate identity or explicit ID drift")
        for brief in briefs:
            detail = request(brief["id"], "https://api.tcgdex.net/v2/en/cards/" + brief["id"])
            if (
                detail.get("id") != brief["id"]
                or detail.get("localId") != brief["localId"]
                or detail.get("name") != brief["name"]
                or detail.get("set", {}).get("id") != "det1"
                or detail.get("language", "en") != "en"
            ):
                raise ValueError("Card identity/language/set conflict")
        ledger["state"] = "complete-acquisition-pending-normalization"
    except (ValueError, KeyError, TypeError) as exc:
        ledger["state"] = "stopped"
        ledger["stop_reason"] = str(exc)
    finally:
        ledger["finished_at"] = now()
        ledger["elapsed_seconds"] = time.monotonic() - start
        ledger["attempts_consumed"] = len(ledger["attempts"])
        ledger["retained_response_bytes"] = sum(a.get("response_bytes", 0) for a in ledger["attempts"])
        ledger["budget_closed"] = True
        save(ledgerpath, ledger)
    print(json.dumps({k: v for k, v in ledger.items() if k != "attempts"}, indent=2))


if __name__ == "__main__":
    run()
