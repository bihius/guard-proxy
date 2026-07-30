"""Dashboard aggregation service — counts, time buckets and top-N over `logs`.

Everything here is computed in SQL rather than by pulling rows into Python:
the dashboard polls these endpoints on a timer, and the `logs` table is the
largest one in the product. All grouped columns (`event_at`, `action`,
`severity`, `source_ip`, `rule_id`, `vhost`) are already indexed by
`app/models/log.py`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Integer, SQLColumnExpression, case, cast, func, or_, select
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.log import Log, LogAction, LogSeverity
from app.models.policy import Policy
from app.models.policy_binding import PolicyBinding
from app.models.vhost import VHost
from app.schemas.stats import (
    MetricValue,
    OverviewResponse,
    StatsWindow,
    TimeseriesBucket,
    TimeseriesResponse,
    TopResponse,
    TopRule,
    TopSourceIp,
    TopVHost,
)
from app.services.ban_list_service import BanListError, BanListService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WindowSpec:
    """How long a window spans and how finely it is bucketed for charting."""

    span: timedelta
    bucket: timedelta

    @property
    def bucket_count(self) -> int:
        return int(self.span.total_seconds() // self.bucket.total_seconds())


# Bucket sizes are chosen so every window yields 12-30 bars: dense enough to
# show a shape, sparse enough to stay readable on a phone. The 30d ceiling
# matches the default log retention (`settings.log_retention_days`) — older
# data has already been purged, so offering a longer window would only ever
# render empty buckets.
WINDOW_SPECS: dict[StatsWindow, WindowSpec] = {
    "1h": WindowSpec(span=timedelta(hours=1), bucket=timedelta(minutes=5)),
    "24h": WindowSpec(span=timedelta(hours=24), bucket=timedelta(hours=1)),
    "7d": WindowSpec(span=timedelta(days=7), bucket=timedelta(hours=6)),
    "30d": WindowSpec(span=timedelta(days=30), bucket=timedelta(days=1)),
}


def utcnow() -> datetime:
    """Naive UTC 'now', matching how `Log.event_at` is stored.

    Mirrors `log_retention.purge_logs_older_than`; kept as a function so tests
    can monkeypatch a fixed clock.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def resolve_window(
    window: StatsWindow,
    now: datetime | None = None,
) -> tuple[datetime, datetime, WindowSpec]:
    """Return (start_at, end_at, spec) for the requested window."""
    spec = WINDOW_SPECS[window]
    end_at = utcnow() if now is None else now
    return end_at - spec.span, end_at, spec


def compute_delta_pct(current: int, previous: int) -> float | None:
    """Percentage change between two counters, rounded to one decimal.

    Returns None when there is no baseline to compare against: "+∞%" is not
    something a dashboard should ever render.
    """
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _metric(current: int, previous: int) -> MetricValue:
    return MetricValue(
        current=current,
        previous=previous,
        delta_pct=compute_delta_pct(current, previous),
    )


def _epoch_seconds(
    dialect_name: str,
    column: SQLColumnExpression[Any],
) -> ColumnElement[int]:
    """Epoch seconds for a naive-UTC datetime column, per SQL dialect.

    SQLite is the only dialect the product ships with today; the Postgres
    branch exists so switching engines never requires rewriting the grouping
    logic.
    """
    if dialect_name == "sqlite":
        return cast(func.strftime("%s", column), Integer)
    return cast(func.extract("epoch", column), Integer)


def bucket_index_expression(
    dialect_name: str,
    column: SQLColumnExpression[Any],
    start_epoch: int,
    bucket_seconds: int,
) -> ColumnElement[int]:
    """0-based bucket index of `column` relative to `start_epoch`.

    Grouping on an integer index rather than a formatted date string keeps
    sub-hour and multi-hour buckets (5 min, 6 h) on the same code path.
    """
    return cast(
        (_epoch_seconds(dialect_name, column) - start_epoch) / bucket_seconds,
        Integer,
    )


def _to_epoch(value: datetime) -> int:
    return int(value.replace(tzinfo=UTC).timestamp())


class StatsService:
    """Read-only aggregations backing the dashboard."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.dialect = db.bind.dialect.name if db.bind is not None else "sqlite"

    # --- overview ------------------------------------------------------------

    def overview(
        self,
        window: StatsWindow,
        *,
        include_banned_ips: bool,
        now: datetime | None = None,
    ) -> OverviewResponse:
        """KPI counters for the window, each compared to the preceding one."""
        start_at, end_at, spec = resolve_window(window, now)
        previous_start = start_at - spec.span

        # One grouped scan covers both halves and all four counters instead of
        # the eight COUNT(*) queries the naive version would need.
        half = case((Log.event_at >= start_at, 1), else_=0).label("half")
        rows = (
            self.db.query(half, Log.action, Log.severity, func.count().label("total"))
            .filter(Log.event_at >= previous_start, Log.event_at < end_at)
            .group_by(half, Log.action, Log.severity)
            .all()
        )

        counters = {
            "requests": [0, 0],
            "blocked": [0, 0],
            "monitored": [0, 0],
            "critical": [0, 0],
        }
        for is_current, action, severity, total in rows:
            index = int(is_current)
            counters["requests"][index] += total
            if action == LogAction.deny:
                counters["blocked"][index] += total
            elif action == LogAction.monitor:
                counters["monitored"][index] += total
            if severity == LogSeverity.critical:
                counters["critical"][index] += total

        return OverviewResponse(
            window=window,
            start_at=start_at,
            end_at=end_at,
            requests=_metric(counters["requests"][1], counters["requests"][0]),
            blocked=_metric(counters["blocked"][1], counters["blocked"][0]),
            monitored=_metric(counters["monitored"][1], counters["monitored"][0]),
            critical=_metric(counters["critical"][1], counters["critical"][0]),
            banned_ips=self._banned_ip_count() if include_banned_ips else None,
            protected_vhosts=self._protected_vhost_count(),
            total_vhosts=self._total_vhost_count(),
            active_policies=self._active_policy_count(),
        )

    def _protected_vhost_count(self) -> int:
        """Active vhosts covered by a policy, directly or via a path binding."""
        statement = (
            select(func.count(func.distinct(VHost.id)))
            .select_from(VHost)
            .outerjoin(PolicyBinding, PolicyBinding.vhost_id == VHost.id)
            .where(
                VHost.is_active.is_(True),
                or_(VHost.policy_id.is_not(None), PolicyBinding.id.is_not(None)),
            )
        )
        return self.db.execute(statement).scalar_one()

    def _total_vhost_count(self) -> int:
        return self.db.execute(
            select(func.count()).select_from(VHost).where(VHost.is_active.is_(True))
        ).scalar_one()

    def _active_policy_count(self) -> int:
        return self.db.execute(
            select(func.count()).select_from(Policy).where(Policy.is_active.is_(True))
        ).scalar_one()

    def _banned_ip_count(self) -> int | None:
        """Distinct currently-banned IPs, or None if the Runtime API is down.

        The ban list lives in HAProxy stick-tables, not the database, so it is
        the one part of the overview that can fail independently. It degrades
        to None rather than propagating — an unreachable stats socket must not
        blank out the metrics that came from the database.
        """
        try:
            entries = BanListService(self.db).list_banned()
        except BanListError:
            logger.warning("dashboard overview: ban list unavailable", exc_info=True)
            return None
        return len({entry.ip for entry in entries if entry.banned})

    # --- timeseries ----------------------------------------------------------

    def timeseries(
        self,
        window: StatsWindow,
        now: datetime | None = None,
    ) -> TimeseriesResponse:
        """Per-bucket allow/deny/monitor counts across the window."""
        start_at, end_at, spec = resolve_window(window, now)
        bucket_seconds = int(spec.bucket.total_seconds())
        bucket_index = bucket_index_expression(
            self.dialect,
            Log.event_at,
            _to_epoch(start_at),
            bucket_seconds,
        ).label("bucket_index")

        rows = (
            self.db.query(bucket_index, Log.action, func.count().label("total"))
            .filter(Log.event_at >= start_at, Log.event_at < end_at)
            .group_by(bucket_index, Log.action)
            .all()
        )

        # Pre-seed every bucket so gaps come back as explicit zeros.
        tallies: list[dict[str, int]] = [
            {"allow": 0, "deny": 0, "monitor": 0} for _ in range(spec.bucket_count)
        ]
        for index, action, total in rows:
            # Clamp: a row landing exactly on `end_at` due to clock skew would
            # otherwise index past the last bucket.
            slot = min(int(index), spec.bucket_count - 1)
            if slot < 0:
                continue
            tallies[slot][str(action)] += total

        buckets = [
            TimeseriesBucket(bucket_at=start_at + spec.bucket * index, **tally)
            for index, tally in enumerate(tallies)
        ]

        return TimeseriesResponse(
            window=window,
            start_at=start_at,
            end_at=end_at,
            bucket_seconds=bucket_seconds,
            buckets=buckets,
        )

    # --- top-N ---------------------------------------------------------------

    def top(
        self,
        window: StatsWindow,
        *,
        limit: int,
        include_ban_state: bool,
        now: datetime | None = None,
    ) -> TopResponse:
        """Most frequent denied rules, source IPs and vhosts in the window."""
        start_at, end_at, _ = resolve_window(window, now)

        def denied() -> Query[Log]:
            return self.db.query(Log).filter(
                Log.action == LogAction.deny,
                Log.event_at >= start_at,
                Log.event_at < end_at,
            )

        total = func.count().label("total")

        rule_rows = (
            denied()
            .with_entities(Log.rule_id, func.max(Log.rule_message), total)
            .filter(Log.rule_id.is_not(None))
            .group_by(Log.rule_id)
            .order_by(total.desc(), Log.rule_id)
            .limit(limit)
            .all()
        )
        ip_rows = (
            denied()
            .with_entities(Log.source_ip, total)
            .group_by(Log.source_ip)
            .order_by(total.desc(), Log.source_ip)
            .limit(limit)
            .all()
        )
        vhost_rows = (
            denied()
            .with_entities(Log.vhost, func.max(Log.vhost_id), total)
            .group_by(Log.vhost)
            .order_by(total.desc(), Log.vhost)
            .limit(limit)
            .all()
        )

        banned = self._banned_ip_set() if include_ban_state else set()

        return TopResponse(
            window=window,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            rules=[
                TopRule(rule_id=rule_id, rule_message=message, count=count)
                for rule_id, message, count in rule_rows
            ],
            source_ips=[
                TopSourceIp(source_ip=ip, count=count, is_banned=ip in banned)
                for ip, count in ip_rows
            ],
            vhosts=[
                TopVHost(vhost=vhost, vhost_id=vhost_id, count=count)
                for vhost, vhost_id, count in vhost_rows
            ],
        )

    def _banned_ip_set(self) -> set[str]:
        """Currently banned IPs, or an empty set if the Runtime API is down."""
        try:
            entries = BanListService(self.db).list_banned()
        except BanListError:
            logger.warning("dashboard top-N: ban list unavailable", exc_info=True)
            return set()
        return {entry.ip for entry in entries if entry.banned}
