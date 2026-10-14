"""Tests for audit-log tailing, offset state, and ingest retries."""

from __future__ import annotations

import io
import json
import logging
import urllib.error
from collections.abc import Callable
from pathlib import Path

import pytest

from app import shipper
from app.config import Settings


@pytest.fixture(autouse=True)
def _reset_running() -> None:
    shipper._running = True


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        ingest_url="http://backend/logs/ingest",
        ingest_secret="secret",
        audit_log_path=str(tmp_path / "audit.log"),
        state_file=str(tmp_path / "offset"),
        poll_interval_seconds=0.01,
        backoff_base_seconds=0.01,
        backoff_max_seconds=0.05,
        request_timeout_seconds=1.0,
    )


def _audit_line(event_id: str) -> bytes:
    event = {
        "transaction": {
            "id": event_id,
            "timestamp": "2026/05/31 13:29:17",
            "client_ip": "203.0.113.7",
            "request": {
                "method": "GET",
                "uri": "/",
                "headers": {"host": ["example.com"]},
            },
        }
    }
    return json.dumps(event, separators=(",", ":")).encode() + b"\n"


def _patch_sleep(
    monkeypatch: pytest.MonkeyPatch,
    on_sleep: Callable[[int], None] | None = None,
) -> None:
    calls = {"n": 0}

    def sleep(_seconds: float) -> None:
        calls["n"] += 1
        if on_sleep is not None:
            on_sleep(calls["n"])

    monkeypatch.setattr(shipper, "_interruptible_sleep", sleep)


def _capture_posts(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[object],
) -> list[str]:
    """Replace ``_post_event`` with a scripted sequence of statuses or errors."""

    posted: list[str] = []
    pending = list(responses)

    def post(_settings: Settings, payload: dict[str, object]) -> int:
        event_id = payload["producer_event_id"]
        assert isinstance(event_id, str)
        posted.append(event_id)
        if not pending:
            shipper._running = False
            return 200
        step = pending.pop(0)
        if isinstance(step, BaseException):
            raise step
        assert isinstance(step, int)
        if step != 200:
            raise urllib.error.HTTPError(
                "http://backend/logs/ingest",
                step,
                "no",
                hdrs=None,  # type: ignore[arg-type]
                fp=io.BytesIO(b"rejected"),
            )
        if not pending:
            shipper._running = False
        return step

    monkeypatch.setattr(shipper, "_post_event", post)
    return posted


def test_legacy_offset_loads_without_identity(tmp_path: Path) -> None:
    path = tmp_path / "offset"
    path.write_text("15\n", encoding="utf-8")
    state = shipper._load_state(str(path))
    assert state.offset == 15
    assert state.st_ino is None
    assert state.st_dev is None


def test_state_json_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "offset"
    original = shipper._ShipperState(offset=15, st_ino=4, st_dev=9)
    shipper._persist_state(str(path), original)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "offset": 15,
        "st_ino": 4,
        "st_dev": 9,
    }
    assert shipper._load_state(str(path)) == original


def test_missing_state_file_is_quiet(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        state = shipper._load_state(str(tmp_path / "missing"))
    assert state.offset == 0
    assert state.st_ino is None
    assert caplog.records == []


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ("", "empty"),
        ("   \n", "empty"),
        ("not-json", "invalid_json"),
        ("{", "invalid_json"),
        ("[]", "invalid_json"),
        ('{"offset": -1}', "invalid_offset"),
        ('{"offset": true}', "invalid_offset"),
        ("{}", "invalid_offset"),
    ],
)
def test_corrupt_state_is_logged_and_replayed(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    body: str,
    reason: str,
) -> None:
    path = tmp_path / "offset"
    path.write_text(body, encoding="utf-8")
    with caplog.at_level(logging.ERROR):
        state = shipper._load_state(str(path))
    assert state == shipper._ShipperState(offset=0)
    assert f"path={path}" in caplog.text
    assert f"reason={reason}" in caplog.text


def test_invalid_identity_keeps_offset(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "offset"
    path.write_text(
        '{"offset": 5, "st_ino": true, "st_dev": 2, "ignored": 1}',
        encoding="utf-8",
    )
    with caplog.at_level(logging.WARNING):
        state = shipper._load_state(str(path))
    assert state == shipper._ShipperState(offset=5)
    assert "invalid file identity" in caplog.text


def test_persist_fsyncs_file_and_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[int] = []

    def track(fd: int) -> None:
        synced.append(fd)

    monkeypatch.setattr(shipper.os, "fsync", track)
    shipper._persist_state(str(tmp_path / "offset"), shipper._ShipperState(offset=4))
    assert len(synced) >= 2


def test_directory_fsync_failure_is_logged_and_state_is_kept(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = {"n": 0}

    def flaky(fd: int) -> None:
        calls["n"] += 1
        if calls["n"] >= 2:
            raise OSError("directory fsync failed")

    monkeypatch.setattr(shipper.os, "fsync", flaky)
    path = tmp_path / "offset"
    with caplog.at_level(logging.WARNING):
        shipper._persist_state(
            str(path), shipper._ShipperState(offset=3, st_ino=1, st_dev=2)
        )
    assert json.loads(path.read_text(encoding="utf-8"))["offset"] == 3
    assert "directory" in caplog.text


def test_ships_each_complete_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    first = _audit_line("a")
    second = _audit_line("b")
    Path(settings.audit_log_path).write_bytes(first + second)
    posted = _capture_posts(monkeypatch, [200, 200])
    _patch_sleep(monkeypatch, lambda _n: setattr(shipper, "_running", False))
    shipper.run(settings)
    assert posted == ["a", "b"]
    state = shipper._load_state(settings.state_file)
    assert state.offset == len(first) + len(second)
    assert state.st_ino == Path(settings.audit_log_path).stat().st_ino


def test_blank_line_advances_without_dead_letter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    Path(settings.audit_log_path).write_bytes(b"\n" + _audit_line("real"))
    posted = _capture_posts(monkeypatch, [200])
    _patch_sleep(monkeypatch, lambda _n: setattr(shipper, "_running", False))
    shipper.run(settings)
    assert posted == ["real"]
    assert not Path(settings.state_file + ".deadletter").exists()


def test_unparseable_and_unmappable_lines_are_dead_lettered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _settings(tmp_path)
    Path(settings.audit_log_path).write_bytes(b"not-json\n[]\n{}\n")
    _capture_posts(monkeypatch, [])
    _patch_sleep(monkeypatch, lambda _n: setattr(shipper, "_running", False))
    with caplog.at_level(logging.WARNING):
        shipper.run(settings)
    records = [
        json.loads(line)
        for line in Path(settings.state_file + ".deadletter")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [record["reason"] for record in records] == [
        "unparseable",
        "non_object",
        "unmappable",
    ]
    assert records[0]["line"] == "not-json\n"
    assert "dropped_total=1 reason=unparseable" in caplog.text
    assert "dropped_total=3 reason=unmappable" in caplog.text
    assert shipper._load_state(settings.state_file).offset == len(b"not-json\n[]\n{}\n")


def test_dead_letter_caps_stored_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    raw = b"x" * 9000 + b"\n"
    Path(settings.audit_log_path).write_bytes(raw)
    _capture_posts(monkeypatch, [])
    _patch_sleep(monkeypatch, lambda _n: setattr(shipper, "_running", False))
    shipper.run(settings)
    record = json.loads(
        Path(settings.state_file + ".deadletter").read_text(encoding="utf-8")
    )
    assert record["reason"] == "unparseable"
    assert len(record["line"]) == 8 * 1024


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_transient_http_status_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    settings = _settings(tmp_path)
    Path(settings.audit_log_path).write_bytes(_audit_line("once"))
    posted = _capture_posts(monkeypatch, [status, 200])
    _patch_sleep(monkeypatch)
    shipper.run(settings)
    assert posted == ["once", "once"]
    assert not Path(settings.state_file + ".deadletter").exists()
    assert shipper._load_state(settings.state_file).offset == len(_audit_line("once"))


def test_http_422_is_dead_lettered_and_advances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    line = _audit_line("bad")
    Path(settings.audit_log_path).write_bytes(line)
    posted = _capture_posts(monkeypatch, [422])
    _patch_sleep(monkeypatch, lambda _n: setattr(shipper, "_running", False))
    shipper.run(settings)
    assert posted == ["bad"]
    record = json.loads(
        Path(settings.state_file + ".deadletter").read_text(encoding="utf-8")
    )
    assert record["reason"] == "http_422"
    assert shipper._load_state(settings.state_file).offset == len(line)


def test_shutdown_during_retry_does_not_advance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    Path(settings.audit_log_path).write_bytes(_audit_line("pending"))

    def post(_settings: Settings, _payload: dict[str, object]) -> int:
        raise urllib.error.URLError("down")

    monkeypatch.setattr(shipper, "_post_event", post)
    _patch_sleep(monkeypatch, lambda _n: setattr(shipper, "_running", False))
    shipper.run(settings)
    assert shipper._load_state(settings.state_file).offset == 0
    assert not Path(settings.state_file + ".deadletter").exists()


@pytest.mark.parametrize("error", [TimeoutError("timed out"), OSError("reset")])
def test_timeout_and_oserror_are_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    settings = _settings(tmp_path)
    line = _audit_line("later")
    Path(settings.audit_log_path).write_bytes(line)
    posted = _capture_posts(monkeypatch, [error, 200])
    _patch_sleep(monkeypatch)
    shipper.run(settings)
    assert posted == ["later", "later"]
    assert shipper._load_state(settings.state_file).offset == len(line)


def test_legacy_offset_on_a_longer_file_does_not_rewind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    first = _audit_line("old")
    second = _audit_line("new")
    Path(settings.audit_log_path).write_bytes(first + second)
    Path(settings.state_file).write_text(str(len(first)), encoding="utf-8")
    posted = _capture_posts(monkeypatch, [200])
    _patch_sleep(monkeypatch, lambda _n: setattr(shipper, "_running", False))
    shipper.run(settings)
    assert posted == ["new"]
    state = shipper._load_state(settings.state_file)
    assert state.offset == len(first) + len(second)
    assert state.st_ino == Path(settings.audit_log_path).stat().st_ino


def test_truncation_rereads_from_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    audit = Path(settings.audit_log_path)
    line = _audit_line("after")
    audit.write_bytes(line)
    stat_result = audit.stat()
    Path(settings.state_file).write_text(
        json.dumps(
            {
                "offset": 5000,
                "st_ino": stat_result.st_ino,
                "st_dev": stat_result.st_dev,
            }
        ),
        encoding="utf-8",
    )
    posted = _capture_posts(monkeypatch, [200])
    _patch_sleep(monkeypatch, lambda _n: setattr(shipper, "_running", False))
    shipper.run(settings)
    assert posted == ["after"]
    assert shipper._load_state(settings.state_file).offset == len(line)


def test_identity_mismatch_on_startup_starts_at_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _settings(tmp_path)
    audit = Path(settings.audit_log_path)
    line = _audit_line("kept")
    audit.write_bytes(line)
    Path(settings.state_file).write_text(
        json.dumps(
            {"offset": 10000, "st_ino": audit.stat().st_ino + 99, "st_dev": 1}
        ),
        encoding="utf-8",
    )
    posted = _capture_posts(monkeypatch, [200])
    _patch_sleep(monkeypatch, lambda _n: setattr(shipper, "_running", False))
    with caplog.at_level(logging.ERROR):
        shipper.run(settings)
    assert posted == ["kept"]
    assert "identity changed" in caplog.text
    state = shipper._load_state(settings.state_file)
    assert state.offset == len(line)
    assert state.st_ino == audit.stat().st_ino


def test_rotation_drains_old_file_then_reads_new_from_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    audit = Path(settings.audit_log_path)
    audit.write_bytes(_audit_line("a"))
    posted = _capture_posts(monkeypatch, [200, 200, 200, 200])

    def rotate(sleep_n: int) -> None:
        if sleep_n != 1:
            shipper._running = False
            return
        with audit.open("ab") as handle:
            handle.write(_audit_line("c"))
        audit.rename(tmp_path / "audit.log.1")
        # Longer than the offset saved after line "a", so a path-only tail
        # would seek into this file and skip its first event.
        audit.write_bytes(_audit_line("d") + _audit_line("b"))

    _patch_sleep(monkeypatch, rotate)
    shipper.run(settings)
    assert posted == ["a", "c", "d", "b"]


def test_rotation_dead_letters_trailing_partial_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    audit = Path(settings.audit_log_path)
    audit.write_bytes(b"partial-without-newline")
    posted = _capture_posts(monkeypatch, [200])

    def rotate(sleep_n: int) -> None:
        if sleep_n != 1:
            shipper._running = False
            return
        audit.rename(tmp_path / "audit.log.1")
        audit.write_bytes(_audit_line("fresh"))

    _patch_sleep(monkeypatch, rotate)
    shipper.run(settings)
    assert posted == ["fresh"]
    record = json.loads(
        Path(settings.state_file + ".deadletter").read_text(encoding="utf-8")
    )
    assert record["reason"] == "truncated_by_rotation"
    assert record["line"] == "partial-without-newline"


def test_overlong_line_is_skipped_and_following_line_ships(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    second = _audit_line("second")
    # The limit fits the following event and splits the poison line.
    monkeypatch.setattr(shipper, "_MAX_LINE_BYTES", len(second))
    Path(settings.audit_log_path).write_bytes(b"x" * len(second) + b"\n" + second)
    posted = _capture_posts(monkeypatch, [200])
    _patch_sleep(monkeypatch, lambda _n: setattr(shipper, "_running", False))
    shipper.run(settings)
    assert posted == ["second"]
    record = json.loads(
        Path(settings.state_file + ".deadletter").read_text(encoding="utf-8")
    )
    assert record["reason"] == "line_too_long"
    assert shipper._load_state(settings.state_file).offset == (
        len(second) + 1 + len(second)
    )


def test_partial_line_waits_until_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    audit = Path(settings.audit_log_path)
    prefix = _audit_line("whole")[:-1]
    audit.write_bytes(prefix)
    posted = _capture_posts(monkeypatch, [200])

    def finish(sleep_n: int) -> None:
        if sleep_n == 1:
            with audit.open("ab") as handle:
                handle.write(b"\n")
            return
        shipper._running = False

    _patch_sleep(monkeypatch, finish)
    shipper.run(settings)
    assert posted == ["whole"]
    assert not Path(settings.state_file + ".deadletter").exists()


def test_overlong_line_waits_until_its_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    audit = Path(settings.audit_log_path)
    following = _audit_line("next")
    monkeypatch.setattr(shipper, "_MAX_LINE_BYTES", len(following))
    audit.write_bytes(b"x" * len(following))
    posted = _capture_posts(monkeypatch, [200])

    def finish(sleep_n: int) -> None:
        if sleep_n == 1:
            with audit.open("ab") as handle:
                handle.write(b"y\n" + following)
            return
        shipper._running = False

    _patch_sleep(monkeypatch, finish)
    shipper.run(settings)
    assert posted == ["next"]
    record = json.loads(
        Path(settings.state_file + ".deadletter").read_text(encoding="utf-8")
    )
    assert record["reason"] == "line_too_long"
