"""Synthetic loopback replay server; acquisition count persists across server restarts."""

import argparse
import json
import socket
from pathlib import Path
from unittest.mock import patch


def run(root, output, port=8011):
    if not (root / "SYNTHETIC_ONLY").is_file():
        raise ValueError("Disposable synthetic state required")
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
    output.mkdir(parents=True, exist_ok=True)
    path = output / "provider-calls.json"
    count = json.loads(path.read_text()) if path.exists() else {"calls": 0, "server_starts": 0}
    count["server_starts"] += 1
    path.write_text(json.dumps(count))

    def prohibited(*args, **kwargs):
        count["calls"] += 1
        path.write_text(json.dumps(count))
        raise AssertionError("Acquisition disabled in the synthetic server")

    from pokemon_hunter.beta.cli import setup

    setup(root)
    if port != 8011:
        # Disposable-only port override retains exact host/origin and loopback checks.
        from pokemon_hunter.beta import security

        def local_port(self, request):
            if (
                request.META.get("HTTP_HOST") != f"127.0.0.1:{port}"
                or request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}
                or any(k == "HTTP_FORWARDED" or k.startswith("HTTP_X_FORWARDED_") for k in request.META)
            ):
                return security.forbidden("Local app is loopback-only")
            origin = request.headers.get("Origin")
            if origin and origin != f"http://127.0.0.1:{port}":
                return security.forbidden("Foreign origin")
            return security.secure_response(self.get_response(request))

        security.LocalOnlyMiddleware.__call__ = local_port
    import uvicorn
    from django.core.asgi import get_asgi_application

    with (
        patch("httpx.Client.send", prohibited),
        patch("httpx.AsyncClient.send", prohibited),
        patch("pokemon_hunter.beta.ebay_hunts.search", prohibited),
        patch("urllib.request.urlopen", prohibited),
    ):
        uvicorn.run(
            get_asgi_application(),
            host="127.0.0.1",
            port=port,
            access_log=False,
            proxy_headers=False,
            log_level="warning",
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--port", type=int, default=8011)
    a = p.parse_args()
    run(a.root, a.output, a.port)
