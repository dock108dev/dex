"""Readiness includes real rendering waits and is independent of driver acknowledgement."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from browser_measurements import isolated_network, navigation_clock, navigation_sample

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


@pytest.mark.parametrize("initial", ["hidden", 'style="width:0;height:0;overflow:hidden"'])
def test_browser_clock_retains_render_wait_and_ignores_late_driver_acknowledgement(initial):
    from playwright.sync_api import sync_playwright

    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = """<div id='primary' INITIAL></div><script nonce='probe'>
            setTimeout(()=>{primary.textContent='Usable content';primary.hidden=false;primary.removeAttribute('style')},150)
            </script>""".replace("INITIAL", initial).encode()
            self.send_response(200)
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'nonce-probe'; connect-src 'self' https://example.invalid; style-src 'unsafe-inline'",
            )
            self.send_header("Cache-Control", "public,max-age=31536000,immutable")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context()
            navigation_clock(context, {"/": "#primary"})
            page = context.new_page()
            blocked = isolated_network(page, base)
            page.goto(base)
            early = page.evaluate("dexNavigation.ready_ms")
            # If the driver was scheduled late, readiness may already be recorded;
            # the browser timestamp must still include the deliberate DOM delay.
            assert early is None or early >= 150
            first = navigation_sample(page)
            assert first["ready_ms"] >= first["visible_ms"] >= 150
            assert page.locator("#primary").inner_text() == "Usable content"
            page.wait_for_timeout(250)
            assert navigation_sample(page) == first
            assert page.evaluate("performance.now()-dexNavigation.ready_ms") >= 250
            for _ in range(2):
                assert page.evaluate("fetch('/cache-proof').then(r=>r.ok)")
            assert requests.count("/cache-proof") == 2
            assert page.evaluate("fetch('https://example.invalid/blocked').then(()=>false,()=>true)")
            assert blocked == ["https://example.invalid/blocked"]
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
