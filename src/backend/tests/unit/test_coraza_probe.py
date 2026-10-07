"""Unit tests for the coraza-spoa SPOP readiness probe."""

from __future__ import annotations

import socket
import struct
import threading
from collections.abc import Iterator

import pytest

from app.services.coraza_probe import (
    decode_varint,
    encode_varint,
    wait_until_served,
)


@pytest.mark.parametrize(
    ("value", "encoded"),
    [
        # Boundaries of the 1-, 2- and 3-byte forms in HAProxy's doc/SPOE.txt.
        (0, b"\x00"),
        (239, b"\xef"),
        (240, b"\xf0\x00"),
        (2287, b"\xff\x7f"),
        (2288, b"\xf0\x80\x00"),
        (264431, b"\xff\xff\x7f"),
    ],
)
def test_varint_matches_spop_encoding(value: int, encoded: bytes) -> None:
    assert encode_varint(value) == encoded
    assert decode_varint(encoded) == (value, len(encoded))


def _read_frame(conn: socket.socket) -> bytes:
    header = conn.recv(4, socket.MSG_WAITALL)
    if len(header) < 4:
        raise ConnectionError
    (length,) = struct.unpack(">I", header)
    return conn.recv(length, socket.MSG_WAITALL)


def _frame(frame_type: int, stream_id: int) -> bytes:
    body = (
        bytes([frame_type]) + struct.pack(">I", 1) + encode_varint(stream_id) + b"\x01"
    )
    return struct.pack(">I", len(body)) + body


def _first_arg_value(body: bytes) -> tuple[int, str]:
    """Stream id and `app` value of a NOTIFY frame."""
    stream_id, offset = decode_varint(body, 5)
    _, offset = decode_varint(body, offset)  # frame id
    name_len, offset = decode_varint(body, offset)
    offset += name_len + 1  # message name, nb-args
    key_len, offset = decode_varint(body, offset)
    offset += key_len + 1  # "app", value type byte
    value_len, offset = decode_varint(body, offset)
    return stream_id, body[offset : offset + value_len].decode()


@pytest.fixture()
def fake_agent() -> Iterator[tuple[int, set[str]]]:
    """A minimal SPOA that, like coraza-spoa, ignores unknown applications."""
    known: set[str] = set()
    server = socket.create_server(("127.0.0.1", 0))
    port = server.getsockname()[1]

    def serve() -> None:
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                return
            with conn:
                try:
                    _read_frame(conn)  # HAPROXY-HELLO
                    conn.sendall(_frame(101, 0))
                    while True:
                        body = _read_frame(conn)
                        if body[0] != 3:  # not NOTIFY: disconnect
                            break
                        stream_id, app = _first_arg_value(body)
                        if app in known:
                            conn.sendall(_frame(103, stream_id))
                except (ConnectionError, OSError):
                    continue

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield port, known
    server.close()


def test_wait_until_served_reports_only_unknown_applications(
    fake_agent: tuple[int, set[str]],
) -> None:
    port, known = fake_agent
    known.update({"default", "policy_1"})

    missing = wait_until_served(
        ["default", "policy_1", "policy_2"],
        host="127.0.0.1",
        port=port,
        timeout_seconds=0.5,
        attempt_timeout_seconds=0.2,
        retry_interval_seconds=0.05,
    )

    assert missing == {"policy_2"}


def test_wait_until_served_returns_once_a_reload_adds_the_application(
    fake_agent: tuple[int, set[str]],
) -> None:
    port, known = fake_agent
    known.add("default")
    threading.Timer(0.3, known.add, args=("policy_1",)).start()

    missing = wait_until_served(
        ["policy_1"],
        host="127.0.0.1",
        port=port,
        timeout_seconds=5,
        attempt_timeout_seconds=0.1,
        retry_interval_seconds=0.05,
    )

    assert missing == set()


def test_wait_until_served_treats_an_unreachable_agent_as_not_ready() -> None:
    with socket.create_server(("127.0.0.1", 0)) as placeholder:
        port = placeholder.getsockname()[1]
    # Nothing listens on `port` any more.

    missing = wait_until_served(
        ["default"],
        host="127.0.0.1",
        port=port,
        timeout_seconds=0.2,
        retry_interval_seconds=0.05,
    )

    assert missing == {"default"}
