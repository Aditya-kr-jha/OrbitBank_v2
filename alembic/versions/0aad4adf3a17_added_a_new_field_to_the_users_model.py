"""added a new field to the users model

Revision ID: 0aad4adf3a17
Revises: 9a71a3838cd7
Create Date: 2025-05-07 10:49:14.944223

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0aad4adf3a17'
down_revision: Union[str, None] = '9a71a3838cd7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
