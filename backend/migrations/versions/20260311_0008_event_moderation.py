"""event moderation

Revision ID: 20260311_0008
Revises: 20260311_0007
Create Date: 2026-03-11 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_0008"
down_revision = "20260311_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("moderation_notes", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("moderated_by_user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_events_moderated_by_user_id"), "events", ["moderated_by_user_id"], unique=False)
    op.create_foreign_key("fk_events_moderated_by_user_id", "events", "users", ["moderated_by_user_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_events_moderated_by_user_id", "events", type_="foreignkey")
    op.drop_index(op.f("ix_events_moderated_by_user_id"), table_name="events")
    op.drop_column("events", "moderated_by_user_id")
    op.drop_column("events", "moderation_notes")