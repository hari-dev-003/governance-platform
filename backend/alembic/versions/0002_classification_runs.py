"""classification runs + run_id on results (idempotent)

Revision ID: b2c3d4e5f6a1
Revises: c059764ee166
Create Date: 2024-01-01 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a1"
down_revision: Union[str, None] = "c059764ee166"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "classification_runs" not in tables:
        op.create_table(
            "classification_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE")),
            sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("data_sources.id")),
            sa.Column("scan_type", sa.String(30), nullable=False),
            sa.Column("engine", sa.String(40), nullable=False),
            sa.Column("columns_scanned", sa.Integer(), server_default=sa.text("0")),
            sa.Column("total_findings", sa.Integer(), server_default=sa.text("0")),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )

    cols = {c["name"] for c in insp.get_columns("classification_results")}
    if "run_id" not in cols:
        op.add_column("classification_results",
                      sa.Column("run_id", postgresql.UUID(as_uuid=True),
                                sa.ForeignKey("classification_runs.id", ondelete="CASCADE"), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("classification_results")}
    if "run_id" in cols:
        op.drop_column("classification_results", "run_id")
    if "classification_runs" in set(insp.get_table_names()):
        op.drop_table("classification_runs")
