from decimal import Decimal
from uuid import uuid4

from app.extensions import db
from app.models.wallet import Wallet, WalletEntry


SIGNUP_BONUS = Decimal("10000.00")


def create_wallet_for_user(user_id: int) -> Wallet:
    wallet = Wallet(user_id=user_id)
    db.session.add(wallet)
    db.session.flush()
    return wallet


def grant_signup_balance(wallet_id: int) -> WalletEntry:
    idempotency_key = f"signup-bonus:{wallet_id}"
    existing_entry = WalletEntry.query.filter_by(idempotency_key=idempotency_key).first()
    if existing_entry:
        return existing_entry

    wallet = Wallet.query.filter_by(id=wallet_id).with_for_update().first()
    if wallet is None:
        raise ValueError("Wallet not found.")

    wallet.current_balance = Decimal(wallet.current_balance) + SIGNUP_BONUS
    entry = WalletEntry(
        wallet_id=wallet.id,
        entry_type="credit",
        amount=SIGNUP_BONUS,
        balance_after=wallet.current_balance,
        reason_code="signup_bonus",
        reference_type="system",
        reference_id=str(wallet.user_id),
        idempotency_key=idempotency_key,
    )
    db.session.add(entry)
    db.session.flush()
    return entry


def create_wallet_entry(
    *,
    wallet_id: int,
    entry_type: str,
    amount: Decimal,
    reason_code: str,
    idempotency_key: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> WalletEntry:
    existing_entry = WalletEntry.query.filter_by(idempotency_key=idempotency_key).first()
    if existing_entry:
        return existing_entry

    wallet = Wallet.query.filter_by(id=wallet_id).with_for_update().first()
    if wallet is None:
        raise ValueError("Wallet not found.")

    normalized_amount = Decimal(amount)
    if entry_type == "debit":
        normalized_amount = -abs(normalized_amount)
    elif entry_type == "credit":
        normalized_amount = abs(normalized_amount)
    else:
        raise ValueError("Unsupported entry type.")

    next_balance = Decimal(wallet.current_balance) + normalized_amount
    if next_balance < Decimal("0.00"):
        raise ValueError("Insufficient balance.")

    wallet.current_balance = next_balance
    entry = WalletEntry(
        wallet_id=wallet.id,
        entry_type=entry_type,
        amount=normalized_amount,
        balance_after=next_balance,
        reason_code=reason_code,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
    )
    db.session.add(entry)
    db.session.flush()
    return entry


def admin_credit_wallet(*, wallet_id: int, amount: Decimal, admin_user_id: int, note: str | None = None) -> WalletEntry:
    normalized_amount = Decimal(amount)
    if normalized_amount <= Decimal("0"):
        raise ValueError("Amount must be greater than zero.")

    return create_wallet_entry(
        wallet_id=wallet_id,
        entry_type="credit",
        amount=normalized_amount,
        reason_code="admin_balance_credit",
        idempotency_key=f"admin-balance-credit:{admin_user_id}:{wallet_id}:{uuid4()}",
        reference_type="admin_user",
        reference_id=str(note or admin_user_id),
    )
