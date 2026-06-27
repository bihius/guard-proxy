"""create custom_rules table

Revision ID: 7da7bf17f2b8
Revises: a43bc7e65317
Create Date: 2026-06-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7da7bf17f2b8"
down_revision: str | Sequence[str] | None = "a43bc7e65317"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "custom_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column(
            "phase",
            sa.Enum(
                "request_headers",
                "request_body",
                "response_headers",
                "response_body",
                "logging",
                name="rulephase",
            ),
            nullable=False,
        ),
        sa.Column("variables", sa.Text(), nullable=False),
        sa.Column(
            "operator",
            sa.Enum(
                "rx",
                "streq",
                "contains",
                "begins_with",
                "ends_with",
                "eq",
                "ge",
                "gt",
                "le",
                "lt",
                "pm",
                "within",
                "ip_match",
                name="ruleoperator",
            ),
            nullable=False,
        ),
        sa.Column("operator_argument", sa.Text(), nullable=False),
        sa.Column("actions", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint(
            "rule_id >= 9000000 AND rule_id <= 9099999",
            name="ck_custom_rules_rule_id_range",
        ),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_id",
            "rule_id",
            name="uq_custom_rules_policy_id_rule_id",
        ),
    )
    op.create_index(
        op.f("ix_custom_rules_policy_id"),
        "custom_rules",
        ["policy_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_custom_rules_policy_id"), table_name="custom_rules")
    op.drop_table("custom_rules")

    # PostgreSQL creates enum types as separate DB objects — drop them explicitly.
    # SQLite has no native enum type, so this block must be skipped there.
    context = op.get_context()
    if context.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS rulephase")
        op.execute("DROP TYPE IF EXISTS ruleoperator")
