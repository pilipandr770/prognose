"""user profile fields

Revision ID: 20260312_0012
Revises: 20260312_0011
Create Date: 2026-03-12 12:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260312_0012"
down_revision = "20260312_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("bio", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("location", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("website_url", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "website_url")
    op.drop_column("users", "location")
    op.drop_column("users", "bio")
    op.drop_column("users", "display_name")
