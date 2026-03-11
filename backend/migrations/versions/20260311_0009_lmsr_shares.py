"""lmsr share model

Revision ID: 20260311_0009
Revises: 20260311_0008
Create Date: 2026-03-11 16:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_0009"
down_revision = "20260311_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("market_liquidity", sa.Numeric(18, 2), nullable=False, server_default="375.00"))
    op.add_column("prediction_positions", sa.Column("share_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"))
    op.add_column("prediction_positions", sa.Column("average_price", sa.Numeric(18, 6), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("prediction_positions", "average_price")
    op.drop_column("prediction_positions", "share_quantity")
    op.drop_column("events", "market_liquidity")