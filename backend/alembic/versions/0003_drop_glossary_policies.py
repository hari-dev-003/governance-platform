"""drop glossary + data_policies tables (feature removed)

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2024-01-02 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a1b2"
down_revision: Union[str, None] = "b2c3d4e5f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for t in ("term_asset_links", "glossary_terms", "data_policies"):
        if t in tables:
            op.drop_table(t)


def downgrade() -> None:
    pass  # one-way removal
