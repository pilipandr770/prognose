from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models.event import Event, EventOutcome
from app.models.prediction import PredictionPosition
from app.models.user import User
from app.services.market_pricing_service import quote_lmsr_trade
from app.services.wallet_service import create_wallet_entry


class PredictionError(ValueError):
    pass


def place_prediction(*, user_id: int, event_id: int, outcome_id: int, stake_amount: Decimal) -> PredictionPosition:
    if Decimal(stake_amount) <= Decimal("0.00"):
        raise PredictionError("Stake amount must be greater than zero.")

    user = User.query.filter_by(id=user_id).first()
    if user is None or user.wallet is None:
        raise PredictionError("User wallet not found.")

    event = Event.query.filter_by(id=event_id).first()
    if event is None:
        raise PredictionError("Event not found.")

    now = datetime.now(timezone.utc)
    closes_at = event.closes_at
    if closes_at.tzinfo is None:
        closes_at = closes_at.replace(tzinfo=timezone.utc)

    if event.status != "open" or closes_at <= now:
        raise PredictionError("Event is closed for new predictions.")

    if PredictionPosition.query.filter_by(user_id=user_id, event_id=event_id).first():
        raise PredictionError("User already has a prediction for this event.")

    outcome = EventOutcome.query.filter_by(id=outcome_id, event_id=event_id).first()
    if outcome is None:
        raise PredictionError("Outcome does not belong to the event.")

    try:
        quote = quote_lmsr_trade(event, outcome_id=outcome_id, budget=Decimal(stake_amount))
    except ValueError as exc:
        raise PredictionError(str(exc)) from exc

    position = PredictionPosition(
        user_id=user_id,
        event_id=event_id,
        outcome_id=outcome_id,
        stake_amount=Decimal(stake_amount),
        share_quantity=Decimal(quote["share_quantity"]),
        average_price=Decimal(quote["average_price"]),
    )
    db.session.add(position)
    db.session.flush()

    create_wallet_entry(
        wallet_id=user.wallet.id,
        entry_type="debit",
        amount=Decimal(stake_amount),
        reason_code="prediction_stake",
        idempotency_key=f"prediction-stake:{position.id}",
        reference_type="prediction_position",
        reference_id=str(position.id),
    )
    db.session.commit()
    return position
