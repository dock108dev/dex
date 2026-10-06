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
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    if args.port not in {8011, 8016}:
        raise ValueError("Only the owner port and private-copy port are allowed")
    if args.port == 8016:
        owner = Path("/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local")
        if args.root.resolve() == owner.resolve() or args.root.name != "profile-root":
            raise ValueError("Alternate port requires the separately backed-up profiling copy")
    setup(args.root)
    if args.port == 8016:
        # Private-copy-only binding substitution; all host/origin/peer guards stay exact.
        from pokemon_hunter.beta import security

        def copied_port(self, request):
            if (
                request.META.get("HTTP_HOST") != "127.0.0.1:8016"
                or request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}
                or any(k == "HTTP_FORWARDED" or k.startswith("HTTP_X_FORWARDED_") for k in request.META)
            ):
                return security.forbidden("Local app is loopback-only")
            origin = request.headers.get("Origin")
            if origin and origin != "http://127.0.0.1:8016":
                return security.forbidden("Foreign origin")
            return security.secure_response(self.get_response(request))

        security.LocalOnlyMiddleware.__call__ = copied_port
    args.evidence.mkdir(mode=0o700, parents=True, exist_ok=False)
    calls = dict(blocked_acquisition_invocations=0, external_requests_sent=0)
    counter = args.evidence / "acquisition-counters.json"
    counter.write_text(json.dumps(calls))

    def blocked(*_args, **_kwargs):
        calls["blocked_acquisition_invocations"] += 1
        counter.write_text(json.dumps(calls))
        raise RuntimeError("Acquisition disabled during M7 owner verification")

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
            port=args.port,
            access_log=False,
            proxy_headers=False,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
