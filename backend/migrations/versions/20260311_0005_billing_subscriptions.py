"""billing and subscriptions

Revision ID: 20260311_0005
Revises: 20260311_0004
Create Date: 2026-03-11 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_0005"
down_revision = "20260311_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("monthly_price", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("stripe_price_id", sa.String(length=128), nullable=True),
        sa.Column("entitlements", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_subscription_plans_code"), "subscription_plans", ["code"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("billing_provider", sa.String(length=32), nullable=False, server_default="internal"),
        sa.Column("provider_customer_id", sa.String(length=128), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=128), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_subscriptions_plan_id"), "subscriptions", ["plan_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_provider_customer_id"), "subscriptions", ["provider_customer_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_provider_subscription_id"), "subscriptions", ["provider_subscription_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_status"), "subscriptions", ["status"], unique=False)
    op.create_index(op.f("ix_subscriptions_user_id"), "subscriptions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_subscriptions_user_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_status"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_provider_subscription_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_provider_customer_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_plan_id"), table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index(op.f("ix_subscription_plans_code"), table_name="subscription_plans")
    op.drop_table("subscription_plans")