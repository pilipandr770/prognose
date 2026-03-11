"""leaderboard snapshots

Revision ID: 20260311_0003
Revises: 20260311_0002
Create Date: 2026-03-11 13:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_0003"
down_revision = "20260311_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leaderboard_snapshots",
        sa.Column("leaderboard_type", sa.String(length=32), nullable=False),
        sa.Column("season_key", sa.String(length=32), nullable=False, server_default="global"),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("leaderboard_type", "season_key", "user_id", name="uq_leaderboard_type_season_user"),
    )
    op.create_index(op.f("ix_leaderboard_snapshots_leaderboard_type"), "leaderboard_snapshots", ["leaderboard_type"], unique=False)
    op.create_index(op.f("ix_leaderboard_snapshots_rank"), "leaderboard_snapshots", ["rank"], unique=False)
    op.create_index(op.f("ix_leaderboard_snapshots_season_key"), "leaderboard_snapshots", ["season_key"], unique=False)
    op.create_index(op.f("ix_leaderboard_snapshots_user_id"), "leaderboard_snapshots", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_leaderboard_snapshots_user_id"), table_name="leaderboard_snapshots")
    op.drop_index(op.f("ix_leaderboard_snapshots_season_key"), table_name="leaderboard_snapshots")
    op.drop_index(op.f("ix_leaderboard_snapshots_rank"), table_name="leaderboard_snapshots")
    op.drop_index(op.f("ix_leaderboard_snapshots_leaderboard_type"), table_name="leaderboard_snapshots")
    op.drop_table("leaderboard_snapshots")