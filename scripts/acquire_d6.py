"""Bounded D6 acquisition; each explicit invocation consumes a persisted operation."""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/d6-20261005"
LIMITS = {"bulk": 2, "discovery": 30, "official": 40, "retailer": 40, "metadata": 20}


def now():
    return datetime.now(UTC).isoformat()


def save(p, d):
    p.write_text(json.dumps(d, indent=2) + "\n")


def acquire(category, key, url):
    OUT.mkdir(exist_ok=True)
    lp = OUT / "source-ledger.json"
    if not lp.exists():
        with lp.open("x") as f:
            json.dump(
                dict(
                    started_at=now(),
                    limits=LIMITS,
                    max_operations=132,
                    max_bytes=250 * 1024 * 1024,
                    max_seconds=5400,
                    per_operation_seconds=30,
                    retries=0,
                    concurrency=1,
                    attempts=[],
                    stopped_hosts=[],
                ),
                f,
            )
    ledger = json.loads(lp.read_text())
    host = urlparse(url).hostname
    attempts = ledger["attempts"]
    used = sum(a.get("response_bytes", 0) + a.get("headers_bytes", 0) for a in attempts)
    elapsed = (datetime.now(UTC) - datetime.fromisoformat(ledger["started_at"])).total_seconds()
    if (
        ledger.get("closed_at")
        or host in ledger["stopped_hosts"]
        or elapsed >= 5400
        or used >= ledger["max_bytes"]
        or len(attempts) >= 132
        or sum(a["category"] == category for a in attempts) >= LIMITS[category]
    ):
        raise ValueError("Closed source or exhausted budget")
    if any(a["url"] == url for a in attempts):
        raise ValueError("Exact URL already attempted; parse cached source")
    raw = OUT / "raw"
    raw.mkdir(exist_ok=True)
    body = raw / (key + ".raw")
    headers = raw / (key + ".headers")
    transport = raw / (key + ".transport.txt")
    if body.exists():
        raise ValueError("Immutable key exists")
    a = dict(
        operation=len(attempts) + 1,
        category=category,
        key=key,
        url=url,
        retrieved_at=now(),
        source_type=category,
        language="en",
        market="US" if category in {"official", "retailer"} else None,
        version_applicability="pending exact source review",
        response_path=str(body.relative_to(ROOT)),
        outcome="reserved-consumed",
    )
    attempts.append(a)
    save(lp, ledger)
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
            str(min(30, 5400 - elapsed)),
            "--max-filesize",
            str(ledger["max_bytes"] - used),
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
        timeout=31,
    )
    transport.write_bytes(result.stderr)
    data = body.read_bytes() if body.exists() else b""
    status = result.stdout.decode(errors="replace")
    a.update(
        finished_at=now(),
        http_status=status,
        transport_exit=result.returncode,
        response_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        headers_bytes=headers.stat().st_size if headers.exists() else 0,
        headers_path=str(headers.relative_to(ROOT)),
        transport_path=str(transport.relative_to(ROOT)),
        outcome="received" if result.returncode == 0 and status == "200" else "failed",
    )
    challenge = status in {"401", "403", "429"} or (
        category in {"official", "retailer"}
        and any(x in data.lower() for x in [b"captcha", b"access denied", b"cf-chl-", b"px-captcha"])
    )
    if challenge:
        a["outcome"] = "denial-or-challenge"
        ledger["stopped_hosts"].append(host)
    save(lp, ledger)
    print(json.dumps(a))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("category", choices=LIMITS)
    p.add_argument("key")
    p.add_argument("url")
    a = p.parse_args()
    acquire(a.category, a.key, a.url)
