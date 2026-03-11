"""portfolio and assets

Revision ID: 20260311_0002
Revises: 20260311_0001
Create Date: 2026-03-11 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_0002"
down_revision = "20260311_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("current_price", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index(op.f("ix_assets_asset_type"), "assets", ["asset_type"], unique=False)
    op.create_index(op.f("ix_assets_symbol"), "assets", ["symbol"], unique=True)

    op.create_table(
        "asset_price_snapshots",
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="manual"),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asset_price_snapshots_asset_id"), "asset_price_snapshots", ["asset_id"], unique=False)

    op.create_table(
        "portfolio_positions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=8), nullable=False, server_default="0"),
        sa.Column("average_cost", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("realized_pnl", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "asset_id", name="uq_portfolio_user_asset"),
    )
    op.create_index(op.f("ix_portfolio_positions_asset_id"), "portfolio_positions", ["asset_id"], unique=False)
    op.create_index(op.f("ix_portfolio_positions_user_id"), "portfolio_positions", ["user_id"], unique=False)

    op.create_table(
        "portfolio_trades",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("position_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("price", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("gross_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["portfolio_positions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolio_trades_asset_id"), "portfolio_trades", ["asset_id"], unique=False)
    op.create_index(op.f("ix_portfolio_trades_position_id"), "portfolio_trades", ["position_id"], unique=False)
    op.create_index(op.f("ix_portfolio_trades_user_id"), "portfolio_trades", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_portfolio_trades_user_id"), table_name="portfolio_trades")
    op.drop_index(op.f("ix_portfolio_trades_position_id"), table_name="portfolio_trades")
    op.drop_index(op.f("ix_portfolio_trades_asset_id"), table_name="portfolio_trades")
    op.drop_table("portfolio_trades")

    op.drop_index(op.f("ix_portfolio_positions_user_id"), table_name="portfolio_positions")
    op.drop_index(op.f("ix_portfolio_positions_asset_id"), table_name="portfolio_positions")
    op.drop_table("portfolio_positions")

    op.drop_index(op.f("ix_asset_price_snapshots_asset_id"), table_name="asset_price_snapshots")
    op.drop_table("asset_price_snapshots")

    op.drop_index(op.f("ix_assets_symbol"), table_name="assets")
    op.drop_index(op.f("ix_assets_asset_type"), table_name="assets")
    op.drop_table("assets")