"""Config apply router — triggers generate + apply pipeline."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.policy import Policy
from app.models.rule_override import RuleOverride
from app.models.user import User
from app.models.vhost import VHost
from app.schemas.config import ConfigApplyResponse, GeneratedConfigOut
from app.services.config_apply import apply as _apply
from app.services.config_generator import generate

router = APIRouter(prefix="/config", tags=["config"])


@router.post("/apply", response_model=ConfigApplyResponse)
def apply_config(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ConfigApplyResponse:
    """Trigger config generate + apply pipeline (admin only)."""
    vhosts = db.query(VHost).all()
    policies = db.query(Policy).all()
    rule_overrides = db.query(RuleOverride).all()

    generated = generate(vhosts, policies, rule_overrides)
    result = _apply(generated)

    return ConfigApplyResponse(
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
