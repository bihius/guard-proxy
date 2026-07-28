"""add geoip fields to policies

Revision ID: 80557e183990
Revises: ea9292cbacec
Create Date: 2026-07-28 15:24:25.952624

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "80557e183990"
down_revision: str | Sequence[str] | None = "ea9292cbacec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("policies") as batch_op:
        batch_op.add_column(
            sa.Column(
                "geoip_mode",
                sa.Enum("off", "allowlist", "blocklist", name="policygeoipmode"),
                nullable=False,
                server_default="off",
            )
        )
        batch_op.add_column(
            sa.Column(
                "geoip_countries",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("policies") as batch_op:
        batch_op.drop_column("geoip_countries")
        batch_op.drop_column("geoip_mode")
    sa.Enum("off", "allowlist", "blocklist", name="policygeoipmode").drop(
        op.get_bind(), checkfirst=True
    )
