"""split policy anomaly thresholds

Revision ID: 8d4f2a6c1b90
Revises: 2c9b5f4e8d31
Create Date: 2026-05-04 18:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d4f2a6c1b90"
down_revision: str | Sequence[str] | None = "2c9b5f4e8d31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _policy_enforcement_enum() -> sa.Enum:
    return sa.Enum("block", "detect_only", name="policyenforcementmode")


def upgrade() -> None:
    """Upgrade schema."""
    context = op.get_context()
    bind = op.get_bind()

    if context.dialect.name == "postgresql":
        _policy_enforcement_enum().create(bind, checkfirst=True)
        enforcement_enum = postgresql.ENUM(
            "block",
            "detect_only",
            name="policyenforcementmode",
            create_type=False,
        )
    else:
        enforcement_enum = _policy_enforcement_enum()

    with op.batch_alter_table("policies") as batch_op:
        batch_op.drop_constraint("ck_policies_anomaly_threshold", type_="check")
        batch_op.add_column(
            sa.Column("inbound_anomaly_threshold", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("outbound_anomaly_threshold", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "enforcement_mode",
                enforcement_enum,
                nullable=False,
                server_default="block",
            )
        )

    op.execute(
        "UPDATE policies "
        "SET inbound_anomaly_threshold = anomaly_threshold, "
        "outbound_anomaly_threshold = anomaly_threshold"
    )

    with op.batch_alter_table("policies") as batch_op:
        batch_op.alter_column("inbound_anomaly_threshold", nullable=False)
        batch_op.alter_column("outbound_anomaly_threshold", nullable=False)
        batch_op.alter_column("enforcement_mode", server_default=None)
        batch_op.drop_column("anomaly_threshold")
        batch_op.create_check_constraint(
            "ck_policies_inbound_anomaly_threshold",
            "inbound_anomaly_threshold >= 1",
        )
        batch_op.create_check_constraint(
            "ck_policies_outbound_anomaly_threshold",
            "outbound_anomaly_threshold >= 1",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("policies") as batch_op:
        batch_op.drop_constraint(
            "ck_policies_outbound_anomaly_threshold",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_policies_inbound_anomaly_threshold",
            type_="check",
        )
        batch_op.add_column(sa.Column("anomaly_threshold", sa.Integer(), nullable=True))

    op.execute("UPDATE policies SET anomaly_threshold = inbound_anomaly_threshold")

    with op.batch_alter_table("policies") as batch_op:
        batch_op.alter_column("anomaly_threshold", nullable=False)
        batch_op.drop_column("enforcement_mode")
        batch_op.drop_column("outbound_anomaly_threshold")
        batch_op.drop_column("inbound_anomaly_threshold")
        batch_op.create_check_constraint(
            "ck_policies_anomaly_threshold",
            "anomaly_threshold >= 0",
        )

    context = op.get_context()
    if context.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS policyenforcementmode")
