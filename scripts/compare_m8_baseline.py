"""Second/final combined check: retained original source on the exact same copy."""

import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

from backup_m6 import dbhashes, filemap
from check_m8_combined import RetainedClock, normalize

if __name__ == "__main__":
    root = Path("/Users/michaelfuscoletti/dex-private/m8-resume-20261006/repaired-restart/profile-root")
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model
    from django.test import RequestFactory
    from django.urls import resolve

    from pokemon_hunter.beta import catalog_imports, offer_filters, packs

    name = "pokemon_hunter.beta._m8_original_catalog_imports"
    spec = importlib.util.spec_from_file_location(
        name, "evidence/m8-resume-20261006/prior-source/catalog_imports.py"
    )
    original = importlib.util.module_from_spec(spec)
    sys.modules[name] = original
    spec.loader.exec_module(original)
    before = dict(tables=dbhashes(root / "inventory.db"), files=filemap(root))
    out = Path("evidence/m8-resume-20261006/combined-parity.json")
    out.write_text(
        json.dumps(
            dict(
                state="second-check-charged",
                requests=2,
                first_comparison="Historical D9 root has independently generated D9 import-journal IDs; exact HTML is incompatible.",
            )
        )
    )
    req = RequestFactory().get("/lookup/?targets=123,134,196,197&scope=all")
    req.user = get_user_model().objects.get(pk=1)

    def blocked(*_args, **_kwargs):
        raise RuntimeError("No external acquisition")

    start = time.perf_counter()
    with (
        patch.object(catalog_imports, "rows_for", original.rows_for),
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
    baseline = response.content.decode()
    (root.parent / "combined-original-source.html").write_text(baseline)
    repaired = (root.parent / "combined-response.html").read_text()
    assert normalize(baseline) == normalize(repaired)
    assert before == dict(tables=dbhashes(root / "inventory.db"), files=filemap(root))
    out.write_text(
        json.dumps(
            dict(
                state="passed",
                total_combined_requests=2,
                complete_html_equal_on_exact_same_state=True,
                csrf_mask_only_normalization=True,
                original_source_seconds=seconds,
                original_source="prior-source/catalog_imports.py; unchanged scalar legacy oracle",
                historical_comparison_failure_retained="D9 journal IDs differ across fresh publication roots; no fields were masked to conceal this",
                common_clock=RetainedClock.now().isoformat(),
                all57tables_and13files_preserved=True,
            ),
            indent=2,
        )
    )
    print("Full combined response exactly matches original source on same copied state")
