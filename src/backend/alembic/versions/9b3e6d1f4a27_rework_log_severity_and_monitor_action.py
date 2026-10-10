"""rework log severity levels and backfill the monitor action

Severity moves from the syslog-style info/warning/error/critical scale, which
the log shipper derived from per-rule CRS severities and a fixed anomaly score,
to low/medium/high relative to each event's policy inbound anomaly threshold.

Existing rows are reclassified in place from their action, anomaly score and
current policy threshold. Allowed rows carrying an anomaly score become
"monitor": coraza-spoa only reports a score through the CRS blocking-evaluation
message, which fires once the threshold is reached, so an allowed event with a
score was a DetectionOnly policy letting a would-be-blocked request through.

Revision ID: 9b3e6d1f4a27
Revises: ecc951b4c672
Create Date: 2026-10-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b3e6d1f4a27"
down_revision: str | Sequence[str] | None = "ecc951b4c672"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_SEVERITIES = ("info", "warning", "error", "critical")
_NEW_SEVERITIES = ("low", "medium", "high")

# Mirrors app.services.config_generator.UNASSIGNED_CRS_POLICY and
# app.services.log_severity; migrations must not import application code.
_UNASSIGNED_INBOUND_THRESHOLD = 5
_HIGH_SEVERITY_THRESHOLD_MULTIPLIER = 2
_THRESHOLD_SQL = (
    "COALESCE((SELECT policies.inbound_anomaly_threshold FROM policies "
    f"WHERE policies.id = logs.policy_id), {_UNASSIGNED_INBOUND_THRESHOLD})"
)


def _severity_enum(values: Sequence[str]) -> sa.Enum:
    return sa.Enum(*values, name="logseverity")


def _is_postgresql() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _literal(value: str) -> str:
    # PostgreSQL resolves an all-literal CASE to text, which has no
    # assignment cast to the native enum.
    return f"'{value}'::logseverity" if _is_postgresql() else f"'{value}'"


def _replace_postgresql_severity_type(values: Sequence[str], using: str) -> None:
    op.execute("ALTER TYPE logseverity RENAME TO logseverity_previous")
    _severity_enum(values).create(op.get_bind())
    op.execute(
        f"ALTER TABLE logs ALTER COLUMN severity TYPE logseverity USING ({using})"
    )
    op.execute("DROP TYPE logseverity_previous")


def _alter_sqlite_severity_type(old: Sequence[str], new: Sequence[str]) -> None:
    with op.batch_alter_table("logs") as batch_op:
        batch_op.alter_column(
            "severity",
            existing_type=_severity_enum(old),
            type_=_severity_enum(new),
            existing_nullable=False,
        )


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE logs SET action = 'monitor' "
        "WHERE action = 'allow' AND anomaly_score IS NOT NULL"
    )

    # The old values carry no information the new scale needs: everything is
    # recomputed below, so the type swap only needs a placeholder value.
    if _is_postgresql():
        _replace_postgresql_severity_type(_NEW_SEVERITIES, "'low'::logseverity")
    else:
        _alter_sqlite_severity_type(_OLD_SEVERITIES, _NEW_SEVERITIES)

    op.execute(
        "UPDATE logs SET severity = CASE "
        "WHEN anomaly_score IS NOT NULL AND anomaly_score >= "
        f"{_HIGH_SEVERITY_THRESHOLD_MULTIPLIER} * {_THRESHOLD_SQL} "
        f"THEN {_literal('high')} "
        "WHEN action <> 'allow' OR "
        f"(anomaly_score IS NOT NULL AND anomaly_score >= {_THRESHOLD_SQL}) "
        f"THEN {_literal('medium')} "
        f"ELSE {_literal('low')} END"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Best-effort inverse of the previous shipper mapping: it never produced
    # "monitor", and its severity came from the action and rule match.
    old_severity_case = (
        "CASE WHEN severity = 'high' THEN 'critical' "
        "WHEN action = 'deny' THEN 'error' "
        "WHEN rule_id IS NOT NULL THEN 'warning' "
        "ELSE 'info' END"
    )
    if _is_postgresql():
        _replace_postgresql_severity_type(
            _OLD_SEVERITIES,
            old_severity_case.replace("severity = ", "severity::text = ")
            + "::logseverity",
        )
    else:
        op.execute(f"UPDATE logs SET severity = {old_severity_case}")
        _alter_sqlite_severity_type(_NEW_SEVERITIES, _OLD_SEVERITIES)

    op.execute("UPDATE logs SET action = 'allow' WHERE action = 'monitor'")
