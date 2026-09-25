"""extend rule exclusion target types; null target_value for single-value targets

Adds REQUEST_URI_RAW, REQUEST_FILENAME, REQUEST_HEADERS_NAMES, REQUEST_COOKIES
and REQUEST_COOKIES_NAMES as exclusion targets. Single-value variables
(REQUEST_URI and the new REQUEST_URI_RAW / REQUEST_FILENAME) have no key, so
target_value becomes nullable and existing REQUEST_URI rows are set to NULL:
the generator never rendered their value.

Revision ID: f3a9c1d7e2b4
Revises: 80557e183990
Create Date: 2026-09-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c1d7e2b4"
down_revision: str | Sequence[str] | None = "80557e183990"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_TARGET_TYPES = ("request_uri", "args", "args_names", "request_headers")
_NEW_TARGET_TYPES = (
    "request_uri_raw",
    "request_filename",
    "request_headers_names",
    "request_cookies",
    "request_cookies_names",
)


def _target_type_enum(values: Sequence[str]) -> sa.Enum:
    return sa.Enum(*values, name="targettype")


def upgrade() -> None:
    """Upgrade schema."""
    is_postgresql = op.get_context().dialect.name == "postgresql"
    # PostgreSQL has a native enum type to extend; ADD VALUE may run inside
    # the migration transaction on 12+ as long as the new values are not used
    # in it. Elsewhere the enum is a VARCHAR sized to the longest value.
    if is_postgresql:
        for value in _NEW_TARGET_TYPES:
            op.execute(f"ALTER TYPE targettype ADD VALUE IF NOT EXISTS '{value}'")

    with op.batch_alter_table("rule_exclusions") as batch_op:
        batch_op.alter_column("target_value", existing_type=sa.Text(), nullable=True)
        if not is_postgresql:
            batch_op.alter_column(
                "target_type",
                existing_type=_target_type_enum(_OLD_TARGET_TYPES),
                type_=_target_type_enum(_OLD_TARGET_TYPES + _NEW_TARGET_TYPES),
                existing_nullable=False,
            )

    op.execute(
        "UPDATE rule_exclusions SET target_value = NULL "
        "WHERE target_type = 'request_uri'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    placeholders = ", ".join(f"'{value}'" for value in _NEW_TARGET_TYPES)
    in_use = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM rule_exclusions "
            f"WHERE target_type IN ({placeholders})"
        )
    ).scalar_one()
    if in_use:
        # The previous schema cannot represent these exclusions; refuse
        # instead of deleting them.
        raise RuntimeError(
            f"{in_use} rule exclusion(s) use target types added in f3a9c1d7e2b4; "
            "delete or change them before downgrading"
        )

    op.execute(
        "UPDATE rule_exclusions SET target_value = 'REQUEST_URI' "
        "WHERE target_value IS NULL"
    )
    with op.batch_alter_table("rule_exclusions") as batch_op:
        batch_op.alter_column("target_value", existing_type=sa.Text(), nullable=False)
        if op.get_context().dialect.name != "postgresql":
            batch_op.alter_column(
                "target_type",
                existing_type=_target_type_enum(_OLD_TARGET_TYPES + _NEW_TARGET_TYPES),
                type_=_target_type_enum(_OLD_TARGET_TYPES),
                existing_nullable=False,
            )
    # PostgreSQL cannot drop enum values; the unused ones stay in targettype.
