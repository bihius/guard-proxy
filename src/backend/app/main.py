import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.config import settings, validate_runtime_settings
from app.database import SessionLocal, get_db
from app.models.custom_rule import CustomRule
from app.models.policy import Policy
from app.models.policy_binding import PolicyBinding
from app.models.rule_exclusion import RuleExclusion
from app.models.rule_override import RuleOverride
from app.models.vhost import VHost
from app.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import (
    auth,
    config,
    custom_rules,
    logs,
    policies,
    rule_exclusions,
    rule_overrides,
    runtime_status,
    vhosts,
)
from app.services.config_apply import seed_runtime_config
from app.services.config_generator import generate
from app.services.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


def _resolve_app_version() -> str:
    """Return the installed package version, the single source of truth.

    Falls back gracefully when the app runs from a source tree that has not
    been installed as a distribution (e.g. some local dev setups).
    """
    try:
        return _package_version("guard-proxy-backend")
    except PackageNotFoundError:  # pragma: no cover - dev-only fallback
        return "0.0.0+unknown"


APP_VERSION = _resolve_app_version()


class _HealthcheckAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if (
            isinstance(args, tuple)
            and len(args) >= 3
            and args[1] == "GET"
            and args[2] in ("/health", "/ready")
        ):
            return False
        return True


logging.getLogger("uvicorn.access").addFilter(_HealthcheckAccessFilter())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan — startup and shutdown events."""
    # Startup
    validate_runtime_settings(settings)
    _seed_runtime_config()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


def _seed_runtime_config() -> None:
    """Seed the runtime config directory from the database, if needed.

    HAProxy and Coraza read their config from the runtime "current"
    release on startup. If no admin has run "Apply config" yet, that
    release does not exist. Best-effort: failures are logged but must not
    block backend startup.
    """
    db = SessionLocal()
    try:
        vhosts = db.query(VHost).options(selectinload(VHost.backends)).all()
        policies = db.query(Policy).all()
        rule_overrides = db.query(RuleOverride).all()
        rule_exclusions = db.query(RuleExclusion).all()
        custom_rules = db.query(CustomRule).all()
        policy_bindings = db.query(PolicyBinding).all()
        generated = generate(
            vhosts,
            policies,
            rule_overrides,
            rule_exclusions,
            custom_rules,
            policy_bindings,
        )
        seed_runtime_config(generated)
    except Exception:
        logger.exception("Failed to seed runtime config on startup")
    finally:
        db.close()



app = FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
    lifespan=lifespan,
)

# --- Rate limiting -----------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]

# --- CORS --------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(config.router)
app.include_router(custom_rules.router)
app.include_router(logs.router)
app.include_router(policies.router)
app.include_router(rule_exclusions.router)
app.include_router(rule_overrides.router)
app.include_router(runtime_status.router)
app.include_router(vhosts.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Liveness probe — always returns 200 if the process is running."""
    return {
        "status": "healthy",
        "version": APP_VERSION,
    }


@app.get("/ready")
def readiness_check(db: Session = Depends(get_db)) -> JSONResponse:
    """Readiness probe — checks DB connectivity and runtime config volume.

    Returns 200 when all checks pass, 503 with a per-check breakdown when any
    dependency is unavailable. Used as the Docker Compose healthcheck gate so
    dependent services (frontend, HAProxy, Coraza) only start once the backend
    can actually serve traffic.
    """
    checks: dict[str, dict[str, str]] = {}
    all_ok = True

    # Check 1: database connectivity
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except SQLAlchemyError as exc:
        logger.error("Readiness DB check failed: %s", exc)
        checks["database"] = {"status": "error", "detail": "database unavailable"}
        all_ok = False

    # Check 2: runtime config volume present and writable (W_OK + X_OK required
    # to create files inside a directory)
    config_root = Path(settings.runtime_generated_config_root)
    if config_root.is_dir() and os.access(config_root, os.W_OK | os.X_OK):
        checks["runtime_config"] = {"status": "ok"}
    else:
        checks["runtime_config"] = {
            "status": "error",
            "detail": f"{config_root} is not a writable directory",
        }
        all_ok = False

    return JSONResponse(
        content={
            "status": "ready" if all_ok else "not ready",
            "checks": checks,
        },
        status_code=200 if all_ok else 503,
    )
