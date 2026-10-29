"""Ordinary CLI lifecycle on a disposable root; only socket/Host mapping is adapted."""

import hashlib
import json
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn

from pokemon_hunter.beta import cli

root, chosen_port = Path(sys.argv[1]), int(sys.argv[2])


def serve(application, **options):
    # Test-only fixed query classes; never SQL text, values or parameters.
    from django.db.backends.signals import connection_created

    from pokemon_hunter.beta.read_diagnostics import current

    profile = []
    lock = threading.Lock()

    def instrument(sender, connection, **kwargs):
        def measure(execute, sql, params, many, context):
            started = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                record = current.get()
                if record is not None:
                    kind = next(
                        (
                            label
                            for needle, label in [
                                ("django_session", "session"),
                                ("auth_user", "authorization"),
                                ("sqlite_master", "infrastructure"),
                                ("cr_gram_index", "search"),
                                ("ar_membership", "membership"),
                                ("account_read_state", "account_manifest"),
                                ("catalog_read_builds", "catalog_manifest"),
                                ("PRAGMA", "connection_setup"),
                            ]
                            if needle in sql
                        ),
                        "other",
                    )
                    with lock:
                        if len(profile) < 5000:
                            profile.append(
                                dict(
                                    id=record["id"],
                                    kind=kind,
                                    query=hashlib.sha256(sql.encode()).hexdigest()[:12],
                                    ms=(time.perf_counter() - started) * 1000,
                                )
                            )

        connection.execute_wrappers.append(measure)

    connection_created.connect(instrument, weak=False)
    original_shutdown = application.shutdown

    def finish():
        original_shutdown()
        (root / "engineering-query-timings.json").write_text(json.dumps(profile))

    application.shutdown = finish
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", chosen_port))

    async def mapped(scope, receive, send):
        started = time.perf_counter()
        if scope["type"] == "http":
            scope = dict(
                scope, headers=[(k, b"127.0.0.1:8011" if k == b"host" else v) for k, v in scope["headers"]]
            )

        async def timed(message):
            if message["type"] == "http.response.start":
                value = f'application;dur={(time.perf_counter() - started) * 1000:.3f}, connection;desc="{scope["client"][1]}"'
                message = dict(message, headers=[*message["headers"], (b"server-timing", value.encode())])
            await send(message)

        return await application(scope, receive, timed)

    class Server(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            print(listener.getsockname()[1], flush=True)

    options.pop("host")
    options.pop("port")
    Server(uvicorn.Config(mapped, **options)).run(sockets=[listener])


uvicorn.run = serve
sys.argv = ["dex", "--root", str(root), "serve"]
cli.entrypoint()
