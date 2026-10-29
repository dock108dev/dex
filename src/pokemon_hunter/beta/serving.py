"""One local ASGI process, one in-flight Django requests, bounded admission wait."""

import asyncio
from time import perf_counter

from .asgi import BoundedBodyApplication

REQUEST_SLOTS = 1
QUEUE_SECONDS = 0.5


class LimitedApplication:
    def __init__(self, application):
        self.application = application
        self.slots = asyncio.Semaphore(REQUEST_SLOTS)
        # This allowlisted static-file view never opens a catalog snapshot.
        self.asset_slots = asyncio.Semaphore(4)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.application(scope, receive, send)
        slots = self.asset_slots if scope.get("path", "").startswith("/collection-assets/") else self.slots
        started = perf_counter()
        try:
            await asyncio.wait_for(slots.acquire(), timeout=QUEUE_SECONDS)
        except TimeoutError:
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
