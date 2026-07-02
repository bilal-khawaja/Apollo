"""test

Revision ID: 4e1cf0638257
Revises: 
Create Date: 2026-07-03 01:46:42.581626

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e1cf0638257'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.drop_column('productcatalogue', 'p_mg')
    op.alter_column('productcatalogue', 'p_name', new_column_name='name')

    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
