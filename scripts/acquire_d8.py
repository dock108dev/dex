"""Bounded immutable D8 public acquisition ledger; no automatic retries."""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/d8-20261006"


def now():
    return datetime.now(UTC).isoformat()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def reserve(category, key, url, method):
    p = OUT / "source-ledger.json"
    d = json.loads(p.read_text())
    if d["started_at"] is None:
        d["started_at"] = now()
    used = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    elapsed = (datetime.now(UTC) - datetime.fromisoformat(d["started_at"])).total_seconds()
    assert not d["closed_at"] and elapsed < 5400 and used < 70 * 1024 * 1024
    assert len(d["attempts"]) < 60
    assert sum(a["category"] == category for a in d["attempts"]) < d["limits"][category]
    assert urlparse(url).hostname not in d["stopped_hosts"]
    assert not any(a["key"] == key for a in d["attempts"])
    prior = [a for a in d["attempts"] if url and a["url"] == url]
    if prior:
        assert len(prior) == 1
        assert (prior[0]["outcome"] == "failed" and prior[0].get("http_status") == "000") or (
            prior[0]["outcome"] == "received" and method == "rendered-browser"
        )
        if prior[0]["outcome"] == "failed":
            assert sum(a.get("retry", False) for a in d["attempts"]) < 4
    a = dict(
        operation=len(d["attempts"]) + 1,
        category=category,
        key=key,
        url=url,
        method=method,
        observed_at=now(),
        outcome="reserved-consumed",
    )
    a["retry"] = bool(prior and prior[0]["outcome"] == "failed")
    a["supplemental_render"] = bool(prior and prior[0]["outcome"] == "received")
    d["attempts"].append(a)
    write(p, d)
    return a


def finish(key, raw, outcome, extra=None):
    p = OUT / "source-ledger.json"
    d = json.loads(p.read_text())
    a = next(x for x in d["attempts"] if x["key"] == key)
    dest = OUT / "raw" / f"{key}.raw"
    assert not dest.exists()
    dest.write_bytes(raw)
    a.update(
        finished_at=now(),
        outcome=outcome,
        response_path=str(dest.relative_to(ROOT)),
        sha256=hashlib.sha256(raw).hexdigest(),
        bytes=len(raw),
        **(extra or {}),
    )
    if outcome == "denial-or-challenge":
        d["stopped_hosts"].append(urlparse(a["url"]).hostname)
    write(p, d)
    return a


if __name__ == "__main__":
    mode, key = sys.argv[1:3]
    if mode == "fetch":
        category, url = sys.argv[3:5]
        reserve(category, key, url, "direct-GET")
        body = OUT / "raw" / f"{key}.pending"
        headers = OUT / "raw" / f"{key}.headers"
        r = subprocess.run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--retry",
                "0",
                "--max-time",
                "30",
                "--max-filesize",
                "5242880",
                "--location",
                "--max-redirs",
                "4",
                "--proto",
                "=https",
                "--proto-redir",
                "=https",
                "--dump-header",
                str(headers),
                "--output",
                str(body),
                "--write-out",
                "%{http_code}\n%{url_effective}",
                url,
            ],
            capture_output=True,
            timeout=32,
        )
        raw = body.read_bytes() if body.exists() else b""
        if body.exists():
            body.unlink()
        status = r.stdout.decode().split("\n")[0]
        low = raw.lower()
        challenge = status in ["401", "403", "429"] or any(
            t in low for t in [b"cf-chl-", b"px-captcha", b"<title>access denied", b"<title>robot or human"]
        )
        a = finish(
            key,
            raw,
            "denial-or-challenge"
            if challenge
            else "received"
            if status == "200" and r.returncode == 0
            else "failed",
            dict(
                http_status=status,
                effective_url=r.stdout.decode().split("\n")[-1],
                transport_exit=r.returncode,
                headers_path=str(headers.relative_to(ROOT)),
                headers_sha256=hashlib.sha256(headers.read_bytes()).hexdigest(),
                transport_error=r.stderr.decode(),
            ),
        )
        print(json.dumps(a))
    elif mode == "reserve":
        print(json.dumps(reserve(sys.argv[3], key, sys.argv[4], sys.argv[5])))
    elif mode == "finish":
        print(json.dumps(finish(key, sys.argv[3].encode(), sys.argv[4])))
