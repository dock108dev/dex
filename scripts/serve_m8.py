"""Copied-runtime request receipts; no owner access or external acquisition."""

import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from serve_m7 import main


def traced_factory(original):
    def factory(*args, **kwargs):
        application = original(*args, **kwargs)
        output = Path(sys.argv[sys.argv.index("--evidence") + 1])

        async def traced(scope, receive, send):
            if scope["type"] != "http":
                return await application(scope, receive, send)
            number = len(list(output.glob("request-*.json"))) + 1
            receipt = output / f"request-{number}.json"
            start = time.perf_counter()
            entry = dict(path=scope["path"], started_utc=datetime.now(UTC).isoformat(), state="started")
            receipt.write_text(json.dumps(entry, indent=2))
            body = bytearray()

            async def record(message):
                if message["type"] == "http.response.start":
                    entry["status"] = message["status"]
                elif message["type"] == "http.response.body":
                    body.extend(message.get("body", b""))
                    if not message.get("more_body", False):
                        entry.update(
                            state="response_complete",
                            seconds=time.perf_counter() - start,
                            bytes=len(body),
                            sha256=hashlib.sha256(body).hexdigest(),
                        )
                        if scope["path"] in {"/api/collection/", "/api/parity/"}:
                            (output / f"response-{number}.json").write_bytes(body)
                        receipt.write_text(json.dumps(entry, indent=2))
                await send(message)

            try:
                await application(scope, receive, record)
            except BaseException as error:
                entry.update(
                    state="exception", exception=type(error).__name__, seconds=time.perf_counter() - start
                )
                receipt.write_text(json.dumps(entry, indent=2))
                raise

        return traced

    return factory


if __name__ == "__main__":
    import django.core.asgi

    with patch(
        "django.core.asgi.get_asgi_application", traced_factory(django.core.asgi.get_asgi_application)
    ):
        main()
