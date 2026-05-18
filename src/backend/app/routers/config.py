"""Config apply router — triggers generate + apply pipeline."""

import threading

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.policy import Policy
from app.models.rule_override import RuleOverride
from app.models.user import User
from app.models.vhost import VHost
from app.schemas.config import ConfigApplyResponse, GeneratedConfigOut
from app.services.config_apply import ApplyStatus, apply as _apply
from app.services.config_generator import generate

router = APIRouter(prefix="/config", tags=["config"])

_apply_lock = threading.Lock()

_HTTP_STATUS: dict[ApplyStatus, int] = {
    ApplyStatus.success: status.HTTP_200_OK,
    ApplyStatus.validation_failed: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ApplyStatus.reload_failed_rolled_back: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ApplyStatus.rollback_failed: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


@router.post("/apply", response_model=ConfigApplyResponse)
def apply_config(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ConfigApplyResponse | JSONResponse:
    """Trigger config generate + apply pipeline (admin only)."""
    if not _apply_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another config apply is already in progress",
        )
    try:
        vhosts = db.query(VHost).all()
        policies = db.query(Policy).all()
        rule_overrides = db.query(RuleOverride).all()

        generated = generate(vhosts, policies, rule_overrides)
        result = _apply(generated)

        response = ConfigApplyResponse(
            generated_config=GeneratedConfigOut(
                haproxy_cfg=generated.haproxy_cfg,
                crs_setup_conf=generated.crs_setup_conf,
                rule_overrides_conf=generated.rule_overrides_conf,
            ),
            status=result.status,
            correlation_id=result.correlation_id,
            checksum=result.checksum,
            message=result.message,
            candidate_path=result.candidate_path,
            active_path=result.active_path,
            validation_output=result.validation_output,
            reload_output=result.reload_output,
            rollback_output=result.rollback_output,
        )

        http_code = _HTTP_STATUS.get(result.status, status.HTTP_500_INTERNAL_SERVER_ERROR)
        if http_code == status.HTTP_200_OK:
            return response
        return JSONResponse(status_code=http_code, content=response.model_dump())
    finally:
        _apply_lock.release()
