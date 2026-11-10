"""Bounded local admission with reserved capacity for indexed browsing."""

import asyncio
import re
from time import perf_counter

from .asgi import BROWSER_HEADERS, BoundedBodyApplication

REQUEST_SLOTS = 1
QUEUE_SECONDS = 0.5


def browsing_read(scope):
    """Reserve one slot for bounded GETs; never move mutations into this lane."""
    if scope.get("method") != "GET":
        return False
    path = scope.get("path", "")
    if path.startswith("/api/v2/"):
        return "/resources/" not in path
    return path in {"/", "/cards/", "/card-library/", "/pokedex/", "/readyz/", "/livez/"} or bool(
        re.fullmatch(r"/(?:pokedex/[0-9]+|card-groups/dg1-[0-9a-f]{64})/", path)
    )


class LimitedApplication:
    def __init__(self, application):
        self.application = application
        self.slots = asyncio.Semaphore(REQUEST_SLOTS)
        # Legacy comparison/report reads can be slow. They must not monopolize
        # admission for indexed browsing. Total dynamic concurrency stays at two.
        self.browse_slots = asyncio.Semaphore(1)
        # This allowlisted static-file view never opens a catalog snapshot.
        self.asset_slots = asyncio.Semaphore(4)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.application(scope, receive, send)
        slots = (
            self.asset_slots
            if scope.get("path", "").startswith("/collection-assets/")
            else self.browse_slots
            if browsing_read(scope)
            else self.slots
        )
        started = perf_counter()
        try:
            await asyncio.wait_for(slots.acquire(), timeout=QUEUE_SECONDS)
        except TimeoutError:
            accepts_html = any(
                key.lower() == b"accept" and b"text/html" in value.lower()
                for key, value in scope.get("headers", [])
            )
            if (
                scope.get("method") == "GET"
                and scope.get("path") in {"/shopping/", "/shopping/check/"}
                and accepts_html
            ):
                body = (
                    b'<!doctype html><html lang="en"><meta charset="utf-8">'
                    b"<title>Dex is busy</title><main><h1>Dex is busy</h1>"
                    b"<p>This page did not start. Your destination is preserved.</p>"
                    b'<a href="" autofocus>Try again</a></main></html>'
                )
                headers = [(k.lower().encode("ascii"), v.encode("ascii")) for k, v in BROWSER_HEADERS.items()]
                headers.extend(
                    [
                        (b"content-type", b"text/html; charset=utf-8"),
                        (b"content-length", str(len(body)).encode()),
                        (b"cache-control", b"no-store"),
                    ]
                )
                await send({"type": "http.response.start", "status": 503, "headers": headers})
                return await send({"type": "http.response.body", "body": body})
            return await BoundedBodyApplication.refuse(send, 503, b'{"error":"runtime_busy"}')
        wait = (perf_counter() - started) * 1000
        try:

            async def timed(message):
                if message["type"] == "http.response.start":
                    message = dict(
                        message,
                        headers=[
                            *message.get("headers", []),
                            (b"server-timing", f"admission;dur={wait:.3f}".encode()),
                        ],
                    )
                await send(message)

            await self.application(scope, receive, timed)
        finally:
            slots.release()


class ShutdownApplication:
    """Join local workers before uvicorn restores/re-raises termination signals."""

    def __init__(self, application, shutdown):
        self.application = application
        self.shutdown = shutdown

    async def __call__(self, scope, receive, send):
        if scope["type"] != "lifespan":
            return await self.application(scope, receive, send)
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await asyncio.to_thread(self.shutdown)
                await send({"type": "lifespan.shutdown.complete"})
                return
