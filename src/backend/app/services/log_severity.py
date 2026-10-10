"""Event severity derived from the WAF verdict and the policy's anomaly threshold.

Per-rule CRS severities are useless as an alert level: almost every attack rule
is tagged "critical", so copying them marks every match as critical. The only
signal that means the same thing across policies is how far the transaction's
anomaly score got relative to the inbound threshold the policy enforces.
"""

from sqlalchemy.orm import Session

from app.models.log import LogAction, LogSeverity
from app.models.policy import Policy
from app.services.config_generator import UNASSIGNED_CRS_POLICY

# A score at this multiple of the threshold matched far more than the minimum
# needed to trip the policy: a clear attack rather than a borderline (and
# possibly false-positive) hit.
HIGH_SEVERITY_THRESHOLD_MULTIPLIER = 2


def classify_severity(
    action: LogAction,
    anomaly_score: int | None,
    inbound_threshold: int,
) -> LogSeverity:
    """Map an event to low/medium/high relative to its inbound threshold.

    - high: score reached ``HIGH_SEVERITY_THRESHOLD_MULTIPLIER`` x threshold.
    - medium: the request was blocked, or would have been (``monitor``), or its
      score reached the threshold.
    - low: rules matched, but the request stayed under the threshold.
    """
    if (
        anomaly_score is not None
        and anomaly_score >= inbound_threshold * HIGH_SEVERITY_THRESHOLD_MULTIPLIER
    ):
        return LogSeverity.high
    if action != LogAction.allow or (
        anomaly_score is not None and anomaly_score >= inbound_threshold
    ):
        return LogSeverity.medium
    return LogSeverity.low


def inbound_threshold_for(db: Session, policy_id: int | None) -> int:
    """Inbound anomaly threshold Coraza enforced for an event's policy.

    Vhosts without a policy run the unassigned CRS defaults; a policy deleted
    since the event was produced falls back to the same defaults.
    """
    if policy_id is not None:
        policy = db.get(Policy, policy_id)
        if policy is not None:
            return policy.inbound_anomaly_threshold
    return UNASSIGNED_CRS_POLICY.inbound_anomaly_threshold
