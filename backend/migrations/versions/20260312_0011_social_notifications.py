"""social notifications inbox

Revision ID: 20260312_0011
Revises: 20260311_0010
Create Date: 2026-03-12 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260312_0011"
down_revision = "20260311_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_notifications",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_social_notifications_actor_user_id"), "social_notifications", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_social_notifications_is_read"), "social_notifications", ["is_read"], unique=False)
    op.create_index(op.f("ix_social_notifications_notification_type"), "social_notifications", ["notification_type"], unique=False)
    op.create_index(op.f("ix_social_notifications_user_id"), "social_notifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_social_notifications_user_id"), table_name="social_notifications")
    op.drop_index(op.f("ix_social_notifications_notification_type"), table_name="social_notifications")
    op.drop_index(op.f("ix_social_notifications_is_read"), table_name="social_notifications")
    op.drop_index(op.f("ix_social_notifications_actor_user_id"), table_name="social_notifications")
    op.drop_table("social_notifications")
