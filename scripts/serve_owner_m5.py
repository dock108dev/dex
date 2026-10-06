"""Owner localhost runtime with acquisition guards and unchanged private settings."""

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from pokemon_hunter.beta.cli import setup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    setup(args.root)
    args.evidence.mkdir(mode=0o700, parents=True, exist_ok=False)
    calls = dict(blocked_acquisition_invocations=0, external_requests_sent=0)
    counter = args.evidence / "acquisition-counters.json"
    counter.write_text(json.dumps(calls))

    def blocked(*_args, **_kwargs):
        calls["blocked_acquisition_invocations"] += 1
        counter.write_text(json.dumps(calls))
        raise RuntimeError("Acquisition disabled during M5 owner verification")

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
