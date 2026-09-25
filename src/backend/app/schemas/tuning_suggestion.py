"""Pydantic schemas for learning-mode tuning suggestions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.rule_exclusion import TargetType
from app.models.tuning_suggestion import SuggestionStatus


class TuningSuggestionResponse(BaseModel):
    """A proposed rule exclusion and the evidence behind it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_id: int
    rule_id: int
    rule_message: str | None
    target_type: TargetType
    target_value: str | None
    scope_path: str | None
    confidence: int
    event_count: int
    source_ip_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    sample_log_ids: list[int]
    status: SuggestionStatus
    rule_exclusion_id: int | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class TuningAnalysisResponse(BaseModel):
    """Result of POST /policies/{id}/suggestions/analyze."""

    events_scanned: int
    created: int
    updated: int
    window_hours: int
