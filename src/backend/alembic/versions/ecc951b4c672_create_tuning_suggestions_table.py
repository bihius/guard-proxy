"""create tuning_suggestions table

Revision ID: ecc951b4c672
Revises: f3a9c1d7e2b4
Create Date: 2026-09-25 14:00:14.859486

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ecc951b4c672"
down_revision: str | Sequence[str] | None = "f3a9c1d7e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TARGET_TYPES = (
    "request_uri",
    "request_uri_raw",
    "request_filename",
    "args",
    "args_names",
    "request_headers",
    "request_headers_names",
    "request_cookies",
    "request_cookies_names",
)


def upgrade() -> None:
    """Upgrade schema."""
    # rule_exclusions already created the PostgreSQL "targettype" type; reuse
    # it instead of letting create_table try to create it again.
    if op.get_context().dialect.name == "postgresql":
        target_type: sa.types.TypeEngine[str] = postgresql.ENUM(
            *_TARGET_TYPES, name="targettype", create_type=False
        )
    else:
        target_type = sa.Enum(*_TARGET_TYPES, name="targettype")

    op.create_table(
        "tuning_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("rule_message", sa.Text(), nullable=True),
        sa.Column("target_type", target_type, nullable=False),
        sa.Column("target_value", sa.Text(), nullable=True),
        sa.Column("scope_path", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("source_ip_count", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("sample_log_ids", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="suggestionstatus"),
            nullable=False,
        ),
        sa.Column("rule_exclusion_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["rule_exclusion_id"], ["rule_exclusions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tuning_suggestions_policy_id"),
        "tuning_suggestions",
        ["policy_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_tuning_suggestions_policy_id"), table_name="tuning_suggestions"
    )
    op.drop_table("tuning_suggestions")
    # "targettype" still belongs to rule_exclusions; only drop our own type.
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS suggestionstatus")
