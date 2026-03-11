"""initial schema

Revision ID: 20260311_0001
Revises:
Create Date: 2026-03-11 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("handle", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("handle"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_handle"), "users", ["handle"], unique=True)

    op.create_table(
        "events",
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False, server_default="binary"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("source_of_truth", sa.String(length=255), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolves_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_outcome_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_category"), "events", ["category"], unique=False)
    op.create_index(op.f("ix_events_closes_at"), "events", ["closes_at"], unique=False)
    op.create_index(op.f("ix_events_creator_id"), "events", ["creator_id"], unique=False)
    op.create_index(op.f("ix_events_resolved_outcome_id"), "events", ["resolved_outcome_id"], unique=False)
    op.create_index(op.f("ix_events_resolves_at"), "events", ["resolves_at"], unique=False)
    op.create_index(op.f("ix_events_status"), "events", ["status"], unique=False)

    op.create_table(
        "wallets",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=16), nullable=False, server_default="GAME_EUR"),
        sa.Column("current_balance", sa.Numeric(precision=18, scale=2), nullable=False, server_default="0"),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_wallets_user_id"), "wallets", ["user_id"], unique=True)

    op.create_table(
        "event_outcomes",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_event_outcomes_event_id"), "event_outcomes", ["event_id"], unique=False)

    op.create_table(
        "wallet_entries",
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("balance_after", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_wallet_entries_idempotency_key"), "wallet_entries", ["idempotency_key"], unique=True)
    op.create_index(op.f("ix_wallet_entries_wallet_id"), "wallet_entries", ["wallet_id"], unique=False)

    op.create_table(
        "prediction_positions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.Integer(), nullable=False),
        sa.Column("stake_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("payout_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["outcome_id"], ["event_outcomes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_id", name="uq_prediction_user_event"),
    )
    op.create_index(op.f("ix_prediction_positions_event_id"), "prediction_positions", ["event_id"], unique=False)
    op.create_index(op.f("ix_prediction_positions_outcome_id"), "prediction_positions", ["outcome_id"], unique=False)
    op.create_index(op.f("ix_prediction_positions_user_id"), "prediction_positions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_prediction_positions_user_id"), table_name="prediction_positions")
    op.drop_index(op.f("ix_prediction_positions_outcome_id"), table_name="prediction_positions")
    op.drop_index(op.f("ix_prediction_positions_event_id"), table_name="prediction_positions")
    op.drop_table("prediction_positions")

    op.drop_index(op.f("ix_wallet_entries_wallet_id"), table_name="wallet_entries")
    op.drop_index(op.f("ix_wallet_entries_idempotency_key"), table_name="wallet_entries")
    op.drop_table("wallet_entries")

    op.drop_index(op.f("ix_event_outcomes_event_id"), table_name="event_outcomes")
    op.drop_table("event_outcomes")

    op.drop_index(op.f("ix_wallets_user_id"), table_name="wallets")
    op.drop_table("wallets")

    op.drop_index(op.f("ix_events_status"), table_name="events")
    op.drop_index(op.f("ix_events_resolves_at"), table_name="events")
    op.drop_index(op.f("ix_events_resolved_outcome_id"), table_name="events")
    op.drop_index(op.f("ix_events_creator_id"), table_name="events")
    op.drop_index(op.f("ix_events_closes_at"), table_name="events")
    op.drop_index(op.f("ix_events_category"), table_name="events")
    op.drop_table("events")

    op.drop_index(op.f("ix_users_handle"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")