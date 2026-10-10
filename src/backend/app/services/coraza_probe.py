"""Check which Coraza applications the running coraza-spoa serves.

HAProxy sends every request to coraza-spoa with the vhost's application name
as the SPOE `app` argument, and coraza-spoa fails the call when it does not
know that name. Config apply uses this probe to hold back the HAProxy reload
until Coraza has loaded every application the new haproxy.cfg references.

There is no API that lists the loaded applications, so the probe asks the
same way HAProxy does: it speaks SPOP (HAProxy's doc/SPOE.txt, protocol 2.0)
and sends one `coraza-req` message per application. coraza-spoa answers with
an ACK when it knows the application and sends nothing when it does not.
The probe message is a plain `GET /` that CRS does not flag, so it leaves no
audit event behind.
"""

from __future__ import annotations

import socket
import struct
import time
from collections.abc import Iterable

_FRAME_HAPROXY_HELLO = 1
_FRAME_HAPROXY_DISCONNECT = 2
_FRAME_NOTIFY = 3
_FRAME_AGENT_HELLO = 101
_FRAME_AGENT_DISCONNECT = 102
_FRAME_ACK = 103
_FLAG_FIN = 1

_TYPE_BOOL = 1
_TYPE_INT32 = 2
_TYPE_UINT32 = 3
_TYPE_IPV4 = 6
_TYPE_STRING = 8
_TYPE_BINARY = 9
_BOOL_TRUE_FLAG = 0x10

# Message name and argument names from configs/haproxy/coraza.cfg.
_MESSAGE_NAME = "coraza-req"
_MAX_FRAME_SIZE = 16380
_PROBE_HEADERS = (
    b"host: guard-proxy-readiness.invalid\r\n"
    b"user-agent: guard-proxy/readiness\r\n"
    b"accept: */*\r\n"
)


class SpopError(Exception):
    """The agent closed the connection or answered with an unexpected frame."""


def encode_varint(value: int) -> bytes:
    """Encode an unsigned integer as an SPOP variable-length integer."""
    if value < 0:
        raise ValueError("SPOP varints are unsigned")
    if value < 240:
        return bytes([value])
    out = bytearray([(value | 240) & 0xFF])
    value = (value - 240) >> 4
    while value >= 128:
        out.append((value | 128) & 0xFF)
        value = (value - 128) >> 7
    out.append(value)
    return bytes(out)


def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    """Decode an SPOP varint; return (value, offset after it)."""
    value = data[offset]
    offset += 1
    if value < 240:
        return value, offset
    shift = 4
    while True:
        byte = data[offset]
        offset += 1
        value += byte << shift
        shift += 7
        if byte < 128:
            return value, offset


def _encode_bytes(value: bytes) -> bytes:
    return encode_varint(len(value)) + value


def _typed_string(value: str) -> bytes:
    return bytes([_TYPE_STRING]) + _encode_bytes(value.encode("utf-8"))


def _typed_binary(value: bytes) -> bytes:
    return bytes([_TYPE_BINARY]) + _encode_bytes(value)


def _typed_uint32(value: int) -> bytes:
    return bytes([_TYPE_UINT32]) + encode_varint(value)


def _typed_int32(value: int) -> bytes:
    return bytes([_TYPE_INT32]) + encode_varint(value)


def _typed_ipv4(value: str) -> bytes:
    return bytes([_TYPE_IPV4]) + socket.inet_aton(value)


def _typed_bool(value: bool) -> bytes:
    return bytes([_TYPE_BOOL | (_BOOL_TRUE_FLAG if value else 0)])


def _kv(name: str, typed_value: bytes) -> bytes:
    return _encode_bytes(name.encode("utf-8")) + typed_value


def _frame(frame_type: int, stream_id: int, frame_id: int, payload: bytes) -> bytes:
    body = (
        bytes([frame_type])
        + struct.pack(">I", _FLAG_FIN)
        + encode_varint(stream_id)
        + encode_varint(frame_id)
        + payload
    )
    return struct.pack(">I", len(body)) + body


def hello_frame() -> bytes:
    payload = (
        _kv("supported-versions", _typed_string("2.0"))
        + _kv("max-frame-size", _typed_uint32(_MAX_FRAME_SIZE))
        + _kv("capabilities", _typed_string(""))
    )
    return _frame(_FRAME_HAPROXY_HELLO, 0, 0, payload)


def disconnect_frame() -> bytes:
    payload = _kv("status-code", _typed_uint32(0)) + _kv(
        "message", _typed_string("normal")
    )
    return _frame(_FRAME_HAPROXY_DISCONNECT, 0, 0, payload)


def notify_frame(app_name: str, stream_id: int) -> bytes:
    """A `coraza-req` message for a benign GET / inspected by `app_name`."""
    # coraza-spoa requires `app` to be the first argument.
    args = (
        _kv("app", _typed_string(app_name)),
        _kv("id", _typed_string(f"guard-proxy-readiness-{stream_id}")),
        _kv("src-ip", _typed_ipv4("127.0.0.1")),
        _kv("src-port", _typed_int32(0)),
        _kv("dst-ip", _typed_ipv4("127.0.0.1")),
        _kv("dst-port", _typed_int32(80)),
        _kv("method", _typed_string("GET")),
        _kv("path", _typed_string("/")),
        _kv("version", _typed_string("1.1")),
        _kv("headers", _typed_binary(_PROBE_HEADERS)),
        _kv("body", _typed_binary(b"")),
        _kv("exportRuleIDs", _typed_bool(False)),
    )
    message = (
        _encode_bytes(_MESSAGE_NAME.encode("utf-8"))
        + bytes([len(args)])
        + b"".join(args)
    )
    return _frame(_FRAME_NOTIFY, stream_id, 1, message)


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise SpopError("agent closed the connection")
        data.extend(chunk)
    return bytes(data)


def _read_frame(conn: socket.socket) -> tuple[int, int]:
    """Read one frame; return (frame type, stream id)."""
    (length,) = struct.unpack(">I", _recv_exact(conn, 4))
    body = _recv_exact(conn, length)
    frame_type = body[0]
    stream_id, _ = decode_varint(body, 5)
    return frame_type, stream_id


def _probe_once(
    address: tuple[str, int],
    app_names: list[str],
    attempt_timeout: float,
) -> set[str]:
    """Return the subset of `app_names` the agent serves right now."""
    served: set[str] = set()
    with socket.create_connection(address, timeout=attempt_timeout) as conn:
        conn.settimeout(attempt_timeout)
        conn.sendall(hello_frame())
        frame_type, _ = _read_frame(conn)
        if frame_type != _FRAME_AGENT_HELLO:
            raise SpopError(f"expected AGENT-HELLO, got frame type {frame_type}")

        for stream_id, name in enumerate(app_names, start=1):
            conn.sendall(notify_frame(name, stream_id))
            try:
                frame_type, ack_stream = _read_frame(conn)
            except TimeoutError:
                # An unknown application makes coraza-spoa drop the message
                # without replying; later messages may still be answered.
                continue
            if frame_type == _FRAME_AGENT_DISCONNECT:
                raise SpopError("agent disconnected")
            if frame_type == _FRAME_ACK and ack_stream == stream_id:
                served.add(name)
        try:
            conn.sendall(disconnect_frame())
        except OSError:
            pass
    return served


def wait_until_served(
    app_names: Iterable[str],
    *,
    host: str,
    port: int,
    timeout_seconds: float,
    attempt_timeout_seconds: float = 1.0,
    retry_interval_seconds: float = 0.2,
) -> set[str]:
    """Poll until coraza-spoa serves every name; return the names still missing.

    An empty result means every application is loaded. Connection errors
    (coraza-spoa restarting, not listening yet) count as "not served yet".
    """
    pending = sorted(set(app_names))
    deadline = time.monotonic() + timeout_seconds
    while pending:
        try:
            served = _probe_once((host, port), pending, attempt_timeout_seconds)
        except (OSError, SpopError):
            served = set()
        pending = [name for name in pending if name not in served]
        if not pending or time.monotonic() >= deadline:
            break
        time.sleep(retry_interval_seconds)
    return set(pending)
