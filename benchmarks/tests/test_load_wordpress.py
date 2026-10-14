"""Exercise the real wrk Lua workload against an HTTP listener."""

import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


@pytest.mark.skipif(
    shutil.which("wrk") is None and (sys.platform != "linux" or shutil.which("docker") is None),
    reason="native wrk or Linux Docker is required",
)
def test_wordpress_load_uses_real_endpoints_and_a_safe_post() -> None:
    seen: set[tuple[str, str, str]] = set()
    posts: set[bytes] = set()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            seen.add(("GET", self.path, self.headers["Host"]))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def do_POST(self) -> None:
            seen.add(("POST", self.path, self.headers["Host"]))
            posts.add(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        script = Path(__file__).resolve().parents[1] / "lab/scenarios/load/benign-mix.lua"
        command = ["wrk", "-t1", "-c1", "-d1s", "-s", str(script), f"http://127.0.0.1:{server.server_port}/"]
        if shutil.which("wrk") is None:
            # The lab and CI use the same pinned wrk image; host networking reaches this listener on Linux.
            command = [
                "docker", "run", "--rm", "--network", "host",
                "-v", f"{script}:/benign-mix.lua:ro",
                "-e", "LOAD_TARGET=wordpress", "-e", "LOAD_VHOST=wp.local",
                "elswork/wrk:4.2.0@sha256:529f8fe35924e549cc270d4128406d5863043e756c31395afd08acccc74ada79",
                "-t1", "-c1", "-d1s", "-s", "/benign-mix.lua", f"http://127.0.0.1:{server.server_port}/",
            ]
        result = subprocess.run(
            command,
            env={**os.environ, "LOAD_TARGET": "wordpress", "LOAD_VHOST": "wp.local"},
            capture_output=True,
            text=True,
            timeout=180,
            check=True,
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join()

    assert "WRK_SUMMARY " in result.stdout
    assert "errors=0" in result.stdout
    assert ("GET", "/", "wp.local") in seen
    assert ("GET", "/wp-json/wp/v2/posts/", "wp.local") in seen
    assert ("POST", "/wp-login.php", "wp.local") in seen
    assert any(b"log=wrk-eval-nonexistent" in body for body in posts)
    assert not any("/products" in path for _, path, _ in seen)
