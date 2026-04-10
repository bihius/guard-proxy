"""add unique constraint for rule overrides

Revision ID: 1f4a7f0f9a11
Revises: 7e0f9c2c9e62
Create Date: 2026-04-10 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1f4a7f0f9a11"
down_revision: Union[str, Sequence[str], None] = "7e0f9c2c9e62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("rule_overrides") as batch_op:
        batch_op.create_unique_constraint(
            "uq_rule_overrides_policy_id_rule_id",
            ["policy_id", "rule_id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("rule_overrides") as batch_op:
        batch_op.drop_constraint(
            "uq_rule_overrides_policy_id_rule_id",
            type_="unique",
        )
