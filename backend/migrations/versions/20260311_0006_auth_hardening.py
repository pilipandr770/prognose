"""auth hardening

Revision ID: 20260311_0006
Revises: 20260311_0005
Create Date: 2026-03-11 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_0006"
down_revision = "20260311_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_login_ip", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("suspicious_activity", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    op.create_table(
        "email_verification_tokens",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(op.f("ix_email_verification_tokens_status"), "email_verification_tokens", ["status"], unique=False)
    op.create_index(op.f("ix_email_verification_tokens_token"), "email_verification_tokens", ["token"], unique=True)
    op.create_index(op.f("ix_email_verification_tokens_user_id"), "email_verification_tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_verification_tokens_user_id"), table_name="email_verification_tokens")
    op.drop_index(op.f("ix_email_verification_tokens_token"), table_name="email_verification_tokens")
    op.drop_index(op.f("ix_email_verification_tokens_status"), table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")

    op.drop_column("users", "suspicious_activity")
    op.drop_column("users", "last_login_ip")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "failed_login_attempts")