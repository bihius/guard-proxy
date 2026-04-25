import logging

from app.main import _HealthcheckAccessFilter


def _access_record(method: str, path: str, status: int = 200) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:12345", method, path, "1.1", status),
        exc_info=None,
    )


def test_healthcheck_access_filter_drops_get_health() -> None:
    assert not _HealthcheckAccessFilter().filter(_access_record("GET", "/health"))


def test_healthcheck_access_filter_keeps_non_get_health() -> None:
    assert _HealthcheckAccessFilter().filter(_access_record("POST", "/health", 405))


def test_healthcheck_access_filter_keeps_non_health_requests() -> None:
    assert _HealthcheckAccessFilter().filter(_access_record("GET", "/api/v1/policies"))
