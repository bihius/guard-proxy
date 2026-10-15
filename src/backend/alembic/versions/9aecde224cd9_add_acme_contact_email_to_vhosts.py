"""add acme contact email to vhosts

Revision ID: 9aecde224cd9
Revises: 9b3e6d1f4a27
Create Date: 2026-10-15 10:40:59.477674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9aecde224cd9'
down_revision: Union[str, Sequence[str], None] = '9b3e6d1f4a27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Deliberately no backfill: rows for certificates issued before this column
    existed stay NULL, and the renewal job then falls back to the old
    admin@<domain> contact. Guessing the issuing admin from created_by would
    re-register the ACME account with an address the certificate never used.
    """
    op.add_column('vhosts', sa.Column('acme_contact_email', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('vhosts', 'acme_contact_email')
