"""Bounded engineering process I/O with ordinary TCP transport semantics."""

import selectors
import socket


def listener():
    # asyncio enables TCP_NODELAY only when sock.proto identifies TCP. A generic
    # protocol-0 socket adds Linux delayed-ACK/Nagle stalls absent from CLI serve.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return sock


def read_port(process, timeout=10):
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        assert selector.select(timeout), "Runtime startup deadline"
    line = process.stdout.readline().strip()
    assert line.isdigit(), "Runtime failed before listening"
    return int(line)


def close_pipes(process):
    for pipe in (process.stdout, process.stderr):
        if pipe is not None:
            pipe.close()
