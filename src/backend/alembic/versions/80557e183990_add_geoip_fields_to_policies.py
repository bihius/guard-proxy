"""add geoip fields to policies

Revision ID: 80557e183990
Revises: ea9292cbacec
Create Date: 2026-07-28 15:24:25.952624

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "80557e183990"
down_revision: str | Sequence[str] | None = "ea9292cbacec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _policy_geoip_mode_enum() -> sa.Enum:
    return sa.Enum("off", "allowlist", "blocklist", name="policygeoipmode")


def upgrade() -> None:
    """Upgrade schema."""
    context = op.get_context()
    bind = op.get_bind()

    # PostgreSQL needs the ENUM type to exist before a column can reference
    # it; add_column does not create it implicitly. Mirrors the pattern used
    # by 8d4f2a6c1b90 for policyenforcementmode.
    if context.dialect.name == "postgresql":
        _policy_geoip_mode_enum().create(bind, checkfirst=True)
        geoip_mode_enum: sa.types.TypeEngine[str] = postgresql.ENUM(
            "off",
            "allowlist",
            "blocklist",
            name="policygeoipmode",
            create_type=False,
        )
    else:
        geoip_mode_enum = _policy_geoip_mode_enum()

    with op.batch_alter_table("policies") as batch_op:
        batch_op.add_column(
            sa.Column(
                "geoip_mode",
                geoip_mode_enum,
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
