import logging

from app.main import _HealthcheckAccessFilter


def _access_record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:12345", "GET", path, "1.1", 200),
        exc_info=None,
    )


def test_healthcheck_access_filter_drops_health_requests() -> None:
    assert not _HealthcheckAccessFilter().filter(_access_record("/health"))


def test_healthcheck_access_filter_keeps_non_health_requests() -> None:
    assert _HealthcheckAccessFilter().filter(_access_record("/api/v1/policies"))
