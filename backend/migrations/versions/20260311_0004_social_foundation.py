"""social foundation

Revision ID: 20260311_0004
Revises: 20260311_0003
Create Date: 2026-03-11 13:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_0004"
down_revision = "20260311_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "follows",
        sa.Column("follower_id", sa.Integer(), nullable=False),
        sa.Column("followee_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["followee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("follower_id", "followee_id", name="uq_follower_followee"),
    )
    op.create_index(op.f("ix_follows_followee_id"), "follows", ["followee_id"], unique=False)
    op.create_index(op.f("ix_follows_follower_id"), "follows", ["follower_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_follows_follower_id"), table_name="follows")
    op.drop_index(op.f("ix_follows_followee_id"), table_name="follows")
    op.drop_table("follows")