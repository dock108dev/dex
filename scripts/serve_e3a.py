"""Disposable SYNTHETIC_ONLY loopback server; prohibited network attempts retained."""

import argparse
import json
import socket
from pathlib import Path
from unittest.mock import patch


def run(root, output):
    if not (root / "SYNTHETIC_ONLY").is_file():
        raise ValueError("Synthetic roots only")
    # Bind check never kills or replaces another server.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 8011))
    output.mkdir(parents=True, exist_ok=True)
    count = {"calls": 0}
    path = output / "provider-calls.json"
    path.write_text(json.dumps(count))

    def prohibited(*args, **kwargs):
        count["calls"] += 1
        path.write_text(json.dumps(count))
        raise AssertionError("E3a prohibits external network/provider calls")

    from pokemon_hunter.beta.cli import setup

    setup(root)
    import uvicorn
    from django.core.asgi import get_asgi_application

    with (
        patch("pokemon_hunter.beta.ebay_hunts.search", prohibited),
        patch("httpx.Client.send", prohibited),
        patch("httpx.AsyncClient.send", prohibited),
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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run(a.root, a.output)
