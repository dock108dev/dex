"""One complete repaired combined response against retained compatible D9 HTML."""

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from backup_m6 import dbhashes, filemap


class RetainedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 10, 6, 19, 14, 36, 516247, tzinfo=UTC)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def normalize(body):
    return re.sub(r'(name="csrfmiddlewaretoken" value=")[^"]+', r"\1REDACTED", body)


if __name__ == "__main__":
    root = Path("/Users/michaelfuscoletti/dex-private/m8-resume-20261006/repaired-restart/profile-root")
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model
    from django.test import RequestFactory
    from django.urls import resolve

    from pokemon_hunter.beta import offer_filters, packs

    before = dict(tables=dbhashes(root / "inventory.db"), files=filemap(root))
    out = Path("evidence/m8-resume-20261006/combined-parity.json")
    out.write_text(json.dumps(dict(state="charged", attempt=1)))
    req = RequestFactory().get("/lookup/?targets=123,134,196,197&scope=all")
    req.user = get_user_model().objects.get(pk=1)

    def blocked(*_args, **_kwargs):
        raise RuntimeError("No external acquisition")

    start = time.perf_counter()
    with (
        patch.object(packs, "datetime", RetainedClock),
        patch.object(offer_filters, "datetime", RetainedClock),
        patch("httpx.Client.send", blocked),
        patch("httpx.AsyncClient.send", blocked),
        patch("urllib.request.urlopen", blocked),
        patch("pokemon_hunter.beta.ebay_hunts.search", blocked),
    ):
        response = resolve(req.path).func(req)
    seconds = time.perf_counter() - start
    assert response.status_code == 200
    body = response.content.decode()
    baseline = Path(
        "/Users/michaelfuscoletti/dex-private/d9-20261006/copied-attempt2/combined-1.response"
    ).read_text()
    private = root.parent / "combined-response.html"
    private.write_text(body)
    assert normalize(body) == normalize(baseline), "Complete combined HTML differs"
    assert before == dict(tables=dbhashes(root / "inventory.db"), files=filemap(root))
    out.write_text(
        json.dumps(
            dict(
                state="passed",
                attempt=1,
                status=200,
                seconds=seconds,
                complete_html_equal=True,
                csrf_mask_only_normalization=True,
                retained_clock=RetainedClock.now(UTC).isoformat(),
                canonical_sha256=hashlib.sha256(normalize(body).encode()).hexdigest(),
                all57tables_and13files_preserved=True,
            ),
            indent=2,
        )
    )
    print("Complete combined HTML equals retained D9 response", seconds)
