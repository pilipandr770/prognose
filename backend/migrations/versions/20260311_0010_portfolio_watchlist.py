"""portfolio watchlist persistence

Revision ID: 20260311_0010
Revises: 20260311_0009
Create Date: 2026-03-11 18:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_0010"
down_revision = "20260311_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_watchlist_items",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "asset_id", name="uq_watchlist_user_asset"),
    )
    op.create_index(op.f("ix_portfolio_watchlist_items_user_id"), "portfolio_watchlist_items", ["user_id"], unique=False)
    op.create_index(op.f("ix_portfolio_watchlist_items_asset_id"), "portfolio_watchlist_items", ["asset_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_portfolio_watchlist_items_asset_id"), table_name="portfolio_watchlist_items")
    op.drop_index(op.f("ix_portfolio_watchlist_items_user_id"), table_name="portfolio_watchlist_items")
    op.drop_table("portfolio_watchlist_items")