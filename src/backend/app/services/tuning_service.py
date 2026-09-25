"""Learning mode: propose rule exclusions for likely false positives (issue #263).

The analyzer groups every rule match in a policy's recent WAF events by
(rule, matched target) and turns frequent groups into pending
TuningSuggestion rows. Nothing is ever applied automatically: an admin
approves a suggestion (possibly after editing it), which creates a
RuleExclusion, or rejects it, which stops it from being proposed again.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.log import Log
from app.models.policy import Policy, PolicyEnforcementMode
from app.models.rule_exclusion import RuleExclusion, TargetType
from app.models.tuning_suggestion import SuggestionStatus, TuningSuggestion
from app.schemas.rule_exclusion import RuleExclusionCreate
from app.services.exclusion_suggestion import (
    exclusion_target,
    iter_rule_matches,
    scope_path_for,
)

# A group needs this many events before it is worth an admin's attention.
MIN_EVENTS = 3
# New suggestions below this confidence are not created: single-client
# bursts that trip several rules at once are attacks, and listing them as
# exclusion candidates invites approving one (or lets an attacker poison the
# window). Existing pending suggestions are still refreshed below it, so their
# numbers never go stale.
MIN_CONFIDENCE = 30
# Bounds the work of one analysis run; the most recent events are kept.
MAX_EVENTS_PER_RUN = 20_000
_SAMPLE_SIZE = 5

_Key = tuple[int, TargetType, str | None]


class TuningError(Exception):
    """Base class for tuning domain errors."""


class TuningPolicyNotFoundError(TuningError):
    pass


class TuningSuggestionNotFoundError(TuningError):
    pass


class TuningSuggestionNotPendingError(TuningError):
    pass


@dataclass(frozen=True)
class AnalysisResult:
    events_scanned: int
    created: int
    updated: int


@dataclass
class _Group:
    rule_message: str | None
    event_count: int = 0
    isolated_count: int = 0
    source_ips: set[str] = field(default_factory=set)
    active_hours: set[datetime] = field(default_factory=set)
    paths: set[str | None] = field(default_factory=set)
    sample_log_ids: deque[int] = field(
        default_factory=lambda: deque(maxlen=_SAMPLE_SIZE)
    )
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def confidence_score(
    event_count: int, source_ip_count: int, active_hours: int, isolated_ratio: float
) -> int:
    """Heuristic 0-100 likelihood that a group of matches is a false positive.

    - Many distinct clients (35): real users trip false positives; a scan or
      an attack usually comes from few addresses, so a single-IP group scores
      low here, which also resists poisoning the learning window.
    - Volume (20): a rule that keeps firing on the same target is systematic.
    - Spread over time (20): false positives follow normal traffic; attacks
      tend to arrive in bursts.
    - Rule fired alone (25): an attack usually trips several rules at once; a
      single rule on an ordinary input is the classic false positive.
    """
    score = (
        35 * min(source_ip_count, 10) / 10
        + 20 * min(event_count, 20) / 20
        + 20 * min(active_hours, 6) / 6
        + 25 * isolated_ratio
    )
    return round(score)


def common_scope_path(paths: set[str | None]) -> str | None:
    """Narrowest scope covering every path, split on "/" segments."""
    if None in paths or not paths:
        return None
    concrete = sorted(p for p in paths if p is not None)
    if len(concrete) == 1:
        return concrete[0]
    split = [p.split("/") for p in concrete]
    common: list[str] = []
    for segments in zip(*split, strict=False):
        if len(set(segments)) != 1:
            break
        common.append(segments[0])
    prefix = "/".join(common)
    if prefix in concrete:
        # One path is the prefix of all others: "/api" covers "/api/x".
        return prefix
    # "/api/users/" covers /api/users/1 and /api/users/2 but not /api/usersX.
    return f"{prefix}/" if prefix else "/"


def _within_scope(path: str, scope: str) -> bool:
    """Segment-aware prefix: "/api" covers "/api" and "/api/x" but not "/apiv2".

    A scope ending in "/" (as produced by common_scope_path) covers everything
    under it.
    """
    if scope.endswith("/"):
        return path.startswith(scope)
    return path == scope or path.startswith(f"{scope}/")


def _is_covered(
    existing: list[RuleExclusion], key: _Key, scope_path: str | None
) -> bool:
    for exclusion in existing:
        if (exclusion.rule_id, exclusion.target_type, exclusion.target_value) != key:
            continue
        if exclusion.scope_path is None:
            return True
        if scope_path is not None and _within_scope(scope_path, exclusion.scope_path):
            return True
    return False


def analyze_policy(
    db: Session, policy_id: int, *, window: timedelta, now: datetime | None = None
) -> AnalysisResult:
    """Create or refresh pending suggestions from the policy's events in `window`."""
    if db.get(Policy, policy_id) is None:
        raise TuningPolicyNotFoundError
    now = now or _utcnow()

    rows = db.execute(
        select(Log.id, Log.event_at, Log.source_ip, Log.request_uri, Log.raw_context)
        .where(Log.policy_id == policy_id, Log.event_at >= now - window)
        .order_by(Log.event_at.desc(), Log.id.desc())
        .limit(MAX_EVENTS_PER_RUN)
    ).all()

    groups: dict[_Key, _Group] = {}
    # Newest first, so the first events seen fill the sample.
    for log_id, event_at, source_ip, request_uri, raw_context in rows:
        matches = [m for m in iter_rule_matches(raw_context) if m.variable is not None]
        rules_in_event = {m.rule_id for m in matches}
        seen_in_event: set[_Key] = set()
        for match in matches:
            assert match.variable is not None
            target = exclusion_target(match.variable, match.key)
            if target is None:
                continue
            key = (match.rule_id, *target)
            if key in seen_in_event:
                continue
            seen_in_event.add(key)
            group = groups.setdefault(key, _Group(rule_message=match.rule_message))
            group.event_count += 1
            group.isolated_count += len(rules_in_event) == 1
            group.source_ips.add(source_ip)
            group.active_hours.add(event_at.replace(minute=0, second=0, microsecond=0))
            group.paths.add(scope_path_for(request_uri))
            if len(group.sample_log_ids) < _SAMPLE_SIZE:
                group.sample_log_ids.append(log_id)
            group.last_seen_at = group.last_seen_at or event_at
            group.first_seen_at = event_at

    exclusions = list(
        db.scalars(select(RuleExclusion).where(RuleExclusion.policy_id == policy_id))
    )
    suggestions = {
        (s.rule_id, s.target_type, s.target_value): s
        for s in db.scalars(
            select(TuningSuggestion).where(TuningSuggestion.policy_id == policy_id)
        )
    }

    created = updated = 0
    for key, group in groups.items():
        if group.event_count < MIN_EVENTS:
            continue
        scope_path = common_scope_path(group.paths)
        if _is_covered(exclusions, key, scope_path):
            continue
        suggestion = suggestions.get(key)
        if suggestion is not None and suggestion.status != SuggestionStatus.pending:
            # Rejected stays rejected; approved already has its exclusion.
            continue
        confidence = confidence_score(
            group.event_count,
            len(group.source_ips),
            len(group.active_hours),
            group.isolated_count / group.event_count,
        )
        if suggestion is None and confidence < MIN_CONFIDENCE:
            continue
        if suggestion is None:
            rule_id, target_type, target_value = key
            suggestion = TuningSuggestion(
                policy_id=policy_id,
                rule_id=rule_id,
                target_type=target_type,
                target_value=target_value,
                status=SuggestionStatus.pending,
            )
            db.add(suggestion)
            created += 1
        else:
            updated += 1
        assert group.first_seen_at is not None and group.last_seen_at is not None
        suggestion.rule_message = group.rule_message
        suggestion.scope_path = scope_path
        suggestion.event_count = group.event_count
        suggestion.source_ip_count = len(group.source_ips)
        suggestion.first_seen_at = group.first_seen_at
        suggestion.last_seen_at = group.last_seen_at
        suggestion.sample_log_ids = list(group.sample_log_ids)
        suggestion.confidence = confidence

    db.commit()
    return AnalysisResult(events_scanned=len(rows), created=created, updated=updated)


def analyze_detect_only_policies(
    db: Session, *, window: timedelta, now: datetime | None = None
) -> dict[int, AnalysisResult]:
    """Learning mode proper: analyze every active policy that only detects."""
    policy_ids = db.scalars(
        select(Policy.id).where(
            Policy.is_active.is_(True),
            Policy.enforcement_mode == PolicyEnforcementMode.detect_only,
        )
    ).all()
    return {
        policy_id: analyze_policy(db, policy_id, window=window, now=now)
        for policy_id in policy_ids
    }


def list_suggestions(
    db: Session, policy_id: int, status: SuggestionStatus | None
) -> list[TuningSuggestion]:
    if db.get(Policy, policy_id) is None:
        raise TuningPolicyNotFoundError
    query = select(TuningSuggestion).where(TuningSuggestion.policy_id == policy_id)
    if status is not None:
        query = query.where(TuningSuggestion.status == status)
    return list(
        db.scalars(
            query.order_by(
                TuningSuggestion.confidence.desc(),
                TuningSuggestion.event_count.desc(),
                TuningSuggestion.id,
            )
        )
    )


def _pending_suggestion(
    db: Session, policy_id: int, suggestion_id: int
) -> TuningSuggestion:
    if db.get(Policy, policy_id) is None:
        raise TuningPolicyNotFoundError
    suggestion = db.get(TuningSuggestion, suggestion_id)
    if suggestion is None or suggestion.policy_id != policy_id:
        raise TuningSuggestionNotFoundError
    if suggestion.status != SuggestionStatus.pending:
        raise TuningSuggestionNotPendingError
    return suggestion


def approve_suggestion(
    db: Session, policy_id: int, suggestion_id: int, exclusion: RuleExclusionCreate
) -> TuningSuggestion:
    """Create the (admin-reviewed) exclusion and resolve the suggestion atomically."""
    suggestion = _pending_suggestion(db, policy_id, suggestion_id)
    rule_exclusion = RuleExclusion(policy_id=policy_id, **exclusion.model_dump())
    db.add(rule_exclusion)
    db.flush()
    suggestion.status = SuggestionStatus.approved
    suggestion.rule_exclusion_id = rule_exclusion.id
    suggestion.resolved_at = _utcnow()
    db.commit()
    db.refresh(suggestion)
    return suggestion


def reject_suggestion(
    db: Session, policy_id: int, suggestion_id: int
) -> TuningSuggestion:
    suggestion = _pending_suggestion(db, policy_id, suggestion_id)
    suggestion.status = SuggestionStatus.rejected
    suggestion.resolved_at = _utcnow()
    db.commit()
    db.refresh(suggestion)
    return suggestion
