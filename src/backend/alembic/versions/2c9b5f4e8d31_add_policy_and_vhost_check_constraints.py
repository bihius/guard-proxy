"""add policy and vhost check constraints

Revision ID: 2c9b5f4e8d31
Revises: 1f4a7f0f9a11, c7a2e5b8f1d0
Create Date: 2026-04-16 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2c9b5f4e8d31"
down_revision: Union[str, Sequence[str], None] = ("1f4a7f0f9a11", "c7a2e5b8f1d0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("policies") as batch_op:
        batch_op.create_check_constraint(
            "ck_policies_paranoia_level",
            "paranoia_level BETWEEN 1 AND 4",
        )
        batch_op.create_check_constraint(
            "ck_policies_anomaly_threshold",
            "anomaly_threshold >= 0",
        )

    with op.batch_alter_table("vhosts") as batch_op:
        batch_op.create_check_constraint(
            "ck_vhosts_domain_lowercase",
            "domain = lower(domain)",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("vhosts") as batch_op:
        batch_op.drop_constraint("ck_vhosts_domain_lowercase", type_="check")

    with op.batch_alter_table("policies") as batch_op:
        batch_op.drop_constraint("ck_policies_anomaly_threshold", type_="check")
        batch_op.drop_constraint("ck_policies_paranoia_level", type_="check")
