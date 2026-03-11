from decimal import Decimal

from app.extensions import db
from app.models.base import BaseModel


class Wallet(BaseModel):
    __tablename__ = "wallets"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    currency_code = db.Column(db.String(16), nullable=False, default="GAME_EUR", server_default="GAME_EUR")
    current_balance = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default="0")

    user = db.relationship("User", back_populates="wallet")
    entries = db.relationship(
        "WalletEntry",
        back_populates="wallet",
        cascade="all, delete-orphan",
        order_by="WalletEntry.id.asc()",
    )


class WalletEntry(BaseModel):
    __tablename__ = "wallet_entries"

    wallet_id = db.Column(db.Integer, db.ForeignKey("wallets.id"), nullable=False, index=True)
    entry_type = db.Column(db.String(16), nullable=False)
    amount = db.Column(db.Numeric(18, 2), nullable=False)
    balance_after = db.Column(db.Numeric(18, 2), nullable=False)
    reason_code = db.Column(db.String(64), nullable=False)
    reference_type = db.Column(db.String(64), nullable=True)
    reference_id = db.Column(db.String(128), nullable=True)
    idempotency_key = db.Column(db.String(128), nullable=False, unique=True, index=True)

    wallet = db.relationship("Wallet", back_populates="entries")
