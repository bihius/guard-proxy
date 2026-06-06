"""Unit tests for app.rate_limit.client_ip()."""

from starlette.requests import Request
from starlette.types import Scope


def _make_request(
    xff: str | None = None,
    client_host: str = "127.0.0.1",
) -> Request:
    """Build a minimal Starlette Request with controlled headers and client."""
    headers: list[tuple[bytes, bytes]] = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode()))
    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/auth/login",
        "headers": headers,
        "client": (client_host, 12345),
        "query_string": b"",
        "root_path": "",
    }
    return Request(scope)


class TestClientIp:
    """client_ip() returns the correct key for rate-limit bucketing."""

    def test_single_xff_returns_that_ip(self) -> None:
        from app.rate_limit import client_ip

        request = _make_request(xff="203.0.113.7")
        assert client_ip(request) == "203.0.113.7"

    def test_multi_value_xff_returns_first_entry(self) -> None:
        """XFF may contain a chain; trust only the leftmost (closest to client)."""
        from app.rate_limit import client_ip

        request = _make_request(xff="10.1.2.3, 172.16.0.1, 192.168.0.5")
        assert client_ip(request) == "10.1.2.3"

    def test_xff_with_extra_whitespace_is_stripped(self) -> None:
        from app.rate_limit import client_ip

        request = _make_request(xff="  198.51.100.42  ")
        assert client_ip(request) == "198.51.100.42"

    def test_no_xff_falls_back_to_socket_peer(self) -> None:
        """Without X-Forwarded-For the socket client address is used (dev / tests)."""
        from app.rate_limit import client_ip

        request = _make_request(xff=None, client_host="192.0.2.99")
        assert client_ip(request) == "192.0.2.99"

    def test_empty_xff_falls_back_to_socket_peer(self) -> None:
        """An empty XFF header (edge case) should not become the key."""
        from app.rate_limit import client_ip

        # Header present but blank → falsy, falls through to get_remote_address
        request = _make_request(xff="", client_host="192.0.2.100")
        assert client_ip(request) == "192.0.2.100"
