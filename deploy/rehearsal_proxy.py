"""Loopback HTTPS proxy for local staging observations only; never production ingress."""

import argparse
import http.client
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--cert", required=True)
parser.add_argument("--key", required=True)
parser.add_argument("--upstream-port", type=int, default=8000)
args = parser.parse_args()


class Proxy(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def forward(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 17_000_000:
            self.send_error(413)
            return
        headers = {
            k: v
            for k, v in self.headers.items()
            if k.lower()
            not in ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "connection")
        }
        headers["X-Forwarded-Proto"] = "https"
        conn = http.client.HTTPConnection("127.0.0.1", args.upstream_port, timeout=60)
        try:
            conn.request(self.command, self.path, self.rfile.read(length), headers)
            response = conn.getresponse()
            body = response.read()
            self.send_response(response.status)
            for k, v in response.getheaders():
                if k.lower() not in ("transfer-encoding", "connection", "server", "date"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
        finally:
            conn.close()

    do_GET = do_POST = do_HEAD = forward


server = ThreadingHTTPServer(("127.0.0.1", 8443), Proxy)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.minimum_version = ssl.TLSVersion.TLSv1_2
context.load_cert_chain(args.cert, args.key)
server.socket = context.wrap_socket(server.socket, server_side=True)
server.serve_forever()
