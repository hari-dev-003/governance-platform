"""Add reference/current dataset refs to monitoring_configs for scheduled drift runs.

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a1b2c3"
down_revision: Union[str, None] = "c3d4e5f6a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: skip if a prior run already added the columns.
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("monitoring_configs")}
    if "reference_dataset_id" not in cols:
        op.add_column("monitoring_configs",
                      sa.Column("reference_dataset_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key("fk_moncfg_reference_dataset", "monitoring_configs", "assets",
                              ["reference_dataset_id"], ["id"], ondelete="SET NULL")
    if "current_dataset_id" not in cols:
        op.add_column("monitoring_configs",
                      sa.Column("current_dataset_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key("fk_moncfg_current_dataset", "monitoring_configs", "assets",
                              ["current_dataset_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_moncfg_current_dataset", "monitoring_configs", type_="foreignkey")
    op.drop_constraint("fk_moncfg_reference_dataset", "monitoring_configs", type_="foreignkey")
    op.drop_column("monitoring_configs", "current_dataset_id")
    op.drop_column("monitoring_configs", "reference_dataset_id")
