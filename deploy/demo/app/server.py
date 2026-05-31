from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class EchoHandler(BaseHTTPRequestHandler):
    server_version = "guard-proxy-demo-echo/0.1"

    def do_GET(self) -> None:
        self._send_echo()

    def do_POST(self) -> None:
        self._send_echo()

    def do_PUT(self) -> None:
        self._send_echo()

    def do_DELETE(self) -> None:
        self._send_echo()

    def _send_echo(self) -> None:
        body = {
            "service": os.getenv("DEMO_APP_NAME", "guard-proxy-demo-echo"),
            "method": self.command,
            "path": self.path,
            "client": self.client_address[0],
            "headers": {
                key: value
                for key, value in self.headers.items()
                if key.lower()
                in {
                    "host",
                    "user-agent",
                    "x-forwarded-for",
                    "x-request-id",
                    "x-waf-score",
                }
            },
        }
        payload = json.dumps(body, indent=2, sort_keys=True).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    app_name = os.getenv("DEMO_APP_NAME", "guard-proxy-demo-echo")
    server = ThreadingHTTPServer(("0.0.0.0", 8080), EchoHandler)
    print(f"{app_name} listening on :8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
