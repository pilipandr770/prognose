from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from app.extensions import db
from app.models.event import Event, EventOutcome
from app.models.prediction import PredictionPosition
from app.models.user import User
from app.services.wallet_service import create_wallet_entry


class EventError(ValueError):
    pass


MIN_EVENT_LEAD_TIME = timedelta(minutes=5)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _lock_expired_event(event: Event, *, now: datetime | None = None) -> bool:
    current_time = now or datetime.now(timezone.utc)
    closes_at = _as_utc(event.closes_at)
    if event.status == "open" and closes_at <= current_time:
        event.status = "locked"
        return True
    return False


def create_event(
    *,
    creator_id: int,
    title: str,
    description: str,
    category: str,
    source_of_truth: str,
    closes_at: datetime,
    resolves_at: datetime,
    outcomes: list[str],
    force_pending_review: bool = False,
) -> Event:
    closes_at = _as_utc(closes_at)
    resolves_at = _as_utc(resolves_at)
    now = datetime.now(timezone.utc)

    if closes_at >= resolves_at:
        raise EventError("closes_at must be earlier than resolves_at.")
    if closes_at <= now + MIN_EVENT_LEAD_TIME:
        raise EventError("closes_at must be at least 5 minutes in the future.")

    normalized_outcomes = [label.strip() for label in outcomes if label and label.strip()]
    if len(normalized_outcomes) < 2:
        raise EventError("At least two outcomes are required.")

    creator = User.query.filter_by(id=creator_id).first()
    if creator is None:
        raise EventError("Creator not found.")

    event_type = "binary" if len(normalized_outcomes) == 2 else "multiple_choice"
    initial_status = "pending_review" if force_pending_review else ("open" if creator.is_admin else "pending_review")
    event = Event(
        creator_id=creator_id,
        title=title.strip(),
        description=description.strip() if description else None,
        category=category.strip().lower(),
        event_type=event_type,
        status=initial_status,
        source_of_truth=source_of_truth.strip(),
        closes_at=closes_at,
        resolves_at=resolves_at,
    )
    db.session.add(event)
    db.session.flush()

    for index, label in enumerate(normalized_outcomes, start=1):
        db.session.add(EventOutcome(event_id=event.id, label=label, position=index))

    db.session.commit()
    return event


def list_open_events() -> list[Event]:
    events = Event.query.filter(Event.status.in_(["open", "locked", "resolved"])).order_by(Event.created_at.desc()).all()
    has_changes = False
    now = datetime.now(timezone.utc)
    for event in events:
        has_changes = _lock_expired_event(event, now=now) or has_changes
    if has_changes:
        db.session.commit()
    return events


def list_pending_events() -> list[Event]:
    return Event.query.filter_by(status="pending_review").order_by(Event.created_at.asc()).all()


def get_event_or_404(event_id: int) -> Event | None:
    event = Event.query.filter_by(id=event_id).first()
    if event is not None and _lock_expired_event(event):
        db.session.commit()
    return event


def resolve_event(*, event_id: int, winning_outcome_id: int, resolver_user_id: int, force_admin: bool = False) -> Event:
    event = Event.query.filter_by(id=event_id).first()
    if event is None:
        raise EventError("Event not found.")

    if not force_admin and event.creator_id != resolver_user_id:
        raise EventError("Only the event creator can resolve this event right now.")

    if event.status == "resolved":
        raise EventError("Event is already resolved.")

    winning_outcome = EventOutcome.query.filter_by(id=winning_outcome_id, event_id=event.id).first()
    if winning_outcome is None:
        raise EventError("Winning outcome does not belong to the event.")

    for position in PredictionPosition.query.filter_by(event_id=event.id).all():
        if position.outcome_id == winning_outcome.id:
            payout_amount = Decimal(position.share_quantity or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            user = User.query.filter_by(id=position.user_id).first()
            create_wallet_entry(
                wallet_id=user.wallet.id,
                entry_type="credit",
                amount=payout_amount,
                reason_code="prediction_payout",
                idempotency_key=f"prediction-payout:{position.id}",
                reference_type="prediction_position",
                reference_id=str(position.id),
            )
            position.status = "won"
            position.payout_amount = payout_amount
        else:
            position.status = "lost"
            position.payout_amount = Decimal("0.00")

    event.status = "resolved"
    event.resolved_outcome_id = winning_outcome.id
    db.session.commit()
    return event


def moderate_event(*, event_id: int, admin_user_id: int, decision: str, notes: str | None = None) -> Event:
    event = Event.query.filter_by(id=event_id).first()
    if event is None:
        raise EventError("Event not found.")
    if event.status not in {"pending_review", "rejected"}:
        raise EventError("Event is not available for moderation.")

    admin_user = User.query.filter_by(id=admin_user_id, is_admin=True).first()
    if admin_user is None:
        raise EventError("Admin user not found.")

    normalized_decision = decision.strip().lower()
    if normalized_decision not in {"approve", "reject"}:
        raise EventError("Decision must be approve or reject.")

    event.status = "open" if normalized_decision == "approve" else "rejected"
    event.moderation_notes = notes.strip() if notes else None
    event.moderated_by_user_id = admin_user.id
    db.session.commit()
    return event
