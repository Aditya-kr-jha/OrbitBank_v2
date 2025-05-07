"""add_is_email_verified_to_users

Revision ID: 1cbc0f8990c7
Revises: 0aad4adf3a17
Create Date: 2025-05-07 10:55:56.922146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1cbc0f8990c7'
down_revision: Union[str, None] = '0aad4adf3a17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
