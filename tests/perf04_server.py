"""Disposable ASGI measurement server. No workers, preparation, or initialization."""

import sys
import time
from pathlib import Path

from runtime_process import listener as tcp_listener

from pokemon_hunter.beta.cli import setup


def main():
    setup(Path(sys.argv[1]))
    import uvicorn

    from pokemon_hunter.beta.asgi import get_asgi_application

    application = get_asgi_application()
    listener = tcp_listener()
    listener.bind(("127.0.0.1", int(sys.argv[2])))
    port = listener.getsockname()[1]

    async def app(scope, receive, send):
        if scope["type"] != "http":
            return await application(scope, receive, send)
        begin = time.perf_counter()
        scope = dict(
            scope,
            headers=[
                (key, b"127.0.0.1:8011" if key == b"host" else value) for key, value in scope["headers"]
            ],
        )

        async def timed(message):
            if message["type"] == "http.response.start":
                timing = f'application;dur={(time.perf_counter() - begin) * 1000:.3f}, connection;desc="{scope["client"][1]}"'
                message = dict(message, headers=[*message["headers"], (b"server-timing", timing.encode())])
            await send(message)

        await application(scope, receive, timed)

    class ReadyServer(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            print(port, flush=True)

    config = uvicorn.Config(app, access_log=False, proxy_headers=False, log_level="error", lifespan="off")
    ReadyServer(config).run(sockets=[listener])


if __name__ == "__main__":
    main()
