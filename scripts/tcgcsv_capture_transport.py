"""One-send HTTPS transport, strict framing and a POSIX request watchdog.

The orchestrator consumes capacity before invoking this adapter. It never
retries, follows redirects, uses credentials or selects additional resources.
"""

import http.client
import signal
import time
from contextlib import contextmanager
from urllib.parse import urlsplit

from scripts.tcgcsv_capture_contract import STEPS, CaptureRefused


class _Response:
    def __init__(self, connection, response):
        self.connection = connection
        self.response = response
        self.status = response.status
        headers = response.getheaders()
        critical = {"content-length", "content-type", "content-encoding", "transfer-encoding"}
        names = [key.lower() for key, _ in headers]
        if any(names.count(key) > 1 for key in critical):
            raise CaptureRefused("duplicate_response_framing")
        self.headers = {key.lower(): value for key, value in headers}
        if "content-length" in self.headers and "transfer-encoding" in self.headers:
            raise CaptureRefused("conflicting_response_framing")
        if self.headers.get("transfer-encoding", "chunked").lower() != "chunked":
            raise CaptureRefused("unsupported_response_framing")

    def read(self, size, timeout):
        if self.response.isclosed():
            return b""
        sock = self.connection.sock or getattr(getattr(self.response.fp, "raw", None), "_sock", None)
        if sock is None:
            raise CaptureRefused("transport_deadline_unavailable")
        sock.settimeout(timeout)
        return self.response.read1(size)


@contextmanager
def _request_deadline(seconds):
    """Main-thread watchdog bounds DNS, TLS, headers and body as one request."""
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if any(previous_timer):
        raise CaptureRefused("request_watchdog_unavailable")

    def expired(_number, _frame):
        raise CaptureRefused("request_deadline_exhausted")

    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


@contextmanager
def transport(url, *, timeout, selected_urls=None):
    """One direct HTTPS GET: no proxy, redirects, retries, auth or fallback."""
    parts = urlsplit(url)
    if url not in (selected_urls or {step[1] for step in STEPS}) or parts.hostname != "tcgcsv.com":
        raise CaptureRefused("unselected_url")
    connection = http.client.HTTPSConnection("tcgcsv.com", timeout=timeout)
    started = time.monotonic()
    try:
        connection.connect()
        connection.sock.settimeout(max(0.001, timeout - (time.monotonic() - started)))
        connection.request(
            "GET",
            parts.path,
            headers={"User-Agent": "Dex/HUNT-11", "Accept-Encoding": "identity", "Connection": "close"},
        )
        connection.sock.settimeout(max(0.001, timeout - (time.monotonic() - started)))
        yield _Response(connection, connection.getresponse())
    finally:
        connection.close()
