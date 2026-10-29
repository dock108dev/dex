"""Regression coverage for the engineering listener and startup pipe."""

import asyncio
import fcntl
import os
import socket
from types import SimpleNamespace

import pytest
from runtime_process import listener, read_port

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


def test_startup_pipe_above_select_descriptor_limit():
    read, write = os.pipe()
    high = fcntl.fcntl(read, fcntl.F_DUPFD, 1100)
    os.close(read)
    try:
        os.write(write, b"12345\n")
        with os.fdopen(high) as pipe:
            assert read_port(SimpleNamespace(stdout=pipe)) == 12345
    finally:
        os.close(write)


def test_listener_accepts_with_ordinary_asyncio_tcp_nodelay():
    async def check():
        accepted = asyncio.Queue()

        class Probe(asyncio.Protocol):
            def connection_made(self, transport):
                sock = transport.get_extra_info("socket")
                accepted.put_nowait(sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY))
                transport.close()

        sock = listener()
        sock.bind(("127.0.0.1", 0))
        server = await asyncio.get_running_loop().create_server(Probe, sock=sock)
        try:
            _, writer = await asyncio.open_connection(*sock.getsockname())
            measured = await asyncio.wait_for(accepted.get(), 2)
            writer.close()
            await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()
        ordinary = await asyncio.get_running_loop().create_server(Probe, host="127.0.0.1", port=0)
        try:
            _, writer = await asyncio.open_connection(*ordinary.sockets[0].getsockname())
            assert measured == await asyncio.wait_for(accepted.get(), 2)
            writer.close()
            await writer.wait_closed()
        finally:
            ordinary.close()
            await ordinary.wait_closed()

    asyncio.run(check())
