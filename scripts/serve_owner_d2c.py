"""Read-only browser qualification runtime; all acquisition paths remain guarded."""

import json
from pathlib import Path
from unittest.mock import patch

from pokemon_hunter.beta.cli import setup

ROOT = Path("/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local")
OUTPUT = Path("/Users/michaelfuscoletti/dex-private/d2c-20261005/browser")


def main():
    OUTPUT.mkdir(mode=0o700, exist_ok=False)
    calls = {"blocked_acquisition_invocations": 0, "external_requests_sent": 0}

    def blocked(*args, **kwargs):
        calls["blocked_acquisition_invocations"] += 1
        (OUTPUT / "acquisition-counters.json").write_text(json.dumps(calls))
        raise RuntimeError("Acquisition disabled during owner collection verification")

    (OUTPUT / "acquisition-counters.json").write_text(json.dumps(calls))
    setup(ROOT)
    import uvicorn
    from django.core.asgi import get_asgi_application

    with (
        patch("httpx.Client.send", blocked),
        patch("httpx.AsyncClient.send", blocked),
        patch("pokemon_hunter.beta.ebay_hunts.search", blocked),
        patch("urllib.request.urlopen", blocked),
    ):
        uvicorn.run(
            get_asgi_application(),
            host="127.0.0.1",
            port=8011,
            access_log=False,
            proxy_headers=False,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
