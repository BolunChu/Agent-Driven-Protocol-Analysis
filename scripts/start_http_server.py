"""Start a minimal local HTTP server for probe validation on port 8080."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer


class ProbeHTTPHandler(BaseHTTPRequestHandler):
    server_version = "ProbeHTTP/1.0"

    def _send_ok(self, body: str = "ok") -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        self._send_ok(f"GET {self.path}")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            _ = self.rfile.read(length)
        self._send_ok(f"POST {self.path}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Allow", "GET,POST,OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt: str, *args):
        return


def main() -> None:
    server = HTTPServer(("127.0.0.1", 8080), ProbeHTTPHandler)
    print("HTTP probe server started on 127.0.0.1:8080")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
