from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.models.prediction import PredictionPosition
from app.services.event_service import EventError, create_event, get_event_or_404, list_open_events, resolve_event
from app.services.market_pricing_service import compute_lmsr_market_state, quote_lmsr_trade
from app.services.prediction_service import PredictionError, place_prediction


events_bp = Blueprint("events", __name__)


def _serialize_event(event):
    market_state = compute_lmsr_market_state(event)
    outcome_prices = {outcome["id"]: outcome for outcome in (market_state or {}).get("outcomes", [])}
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "category": event.category,
        "event_type": event.event_type,
        "status": event.status,
        "market_liquidity": str(event.market_liquidity),
        "source_of_truth": event.source_of_truth,
        "closes_at": event.closes_at.isoformat(),
        "resolves_at": event.resolves_at.isoformat(),
        "resolved_outcome_id": event.resolved_outcome_id,
        "moderation_notes": event.moderation_notes,
        "market_state": market_state,
        "outcomes": [
            {
                "id": outcome.id,
                "label": outcome.label,
                "position": outcome.position,
                "price": str(outcome_prices.get(outcome.id, {}).get("price", "0.5")),
                "probability_pct": str(outcome_prices.get(outcome.id, {}).get("probability_pct", "50")),
                "inventory": str(outcome_prices.get(outcome.id, {}).get("inventory", "0.00")),
            }
            for outcome in event.outcomes
        ],
    }


@events_bp.get("/events")
def list_events():
    events = list_open_events()
    return jsonify({"items": [_serialize_event(event) for event in events]})


@events_bp.post("/events")
@jwt_required()
def create_event_endpoint():
    payload = request.get_json(silent=True) or {}
    required_fields = ["title", "category", "source_of_truth", "closes_at", "resolves_at", "outcomes"]
    missing_fields = [field for field in required_fields if not payload.get(field)]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    try:
        event = create_event(
            creator_id=int(get_jwt_identity()),
            title=payload["title"],
            description=payload.get("description") or "",
            category=payload["category"],
            source_of_truth=payload["source_of_truth"],
            closes_at=datetime.fromisoformat(payload["closes_at"].replace("Z", "+00:00")),
            resolves_at=datetime.fromisoformat(payload["resolves_at"].replace("Z", "+00:00")),
            outcomes=payload["outcomes"],
        )
    except (ValueError, EventError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"event": _serialize_event(event)}), 201


@events_bp.get("/events/<int:event_id>")
def event_detail(event_id: int):
    event = get_event_or_404(event_id)
    if event is None:
        return jsonify({"error": "Event not found."}), 404

    prediction_count = PredictionPosition.query.filter_by(event_id=event.id).count()
    payload = _serialize_event(event)
    payload["prediction_count"] = prediction_count
    return jsonify({"event": payload})


@events_bp.post("/events/<int:event_id>/quote")
@jwt_required()
def quote_prediction_endpoint(event_id: int):
    event = get_event_or_404(event_id)
    if event is None:
        return jsonify({"error": "Event not found."}), 404

    payload = request.get_json(silent=True) or {}
    if payload.get("outcome_id") is None or payload.get("stake_amount") is None:
        return jsonify({"error": "outcome_id and stake_amount are required."}), 400

    try:
        quote = quote_lmsr_trade(
            event,
            outcome_id=int(payload["outcome_id"]),
            budget=Decimal(str(payload["stake_amount"])),
        )
    except (InvalidOperation, TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"quote": quote, "event": _serialize_event(event)})


@events_bp.post("/events/<int:event_id>/predictions")
@jwt_required()
def place_prediction_endpoint(event_id: int):
    payload = request.get_json(silent=True) or {}
    if payload.get("outcome_id") is None or payload.get("stake_amount") is None:
        return jsonify({"error": "outcome_id and stake_amount are required."}), 400

    try:
        stake_amount = Decimal(str(payload["stake_amount"]))
    except (InvalidOperation, TypeError):
        return jsonify({"error": "stake_amount must be a valid decimal value."}), 400

    try:
        position = place_prediction(
            user_id=int(get_jwt_identity()),
            event_id=event_id,
            outcome_id=int(payload["outcome_id"]),
            stake_amount=stake_amount,
        )
    except PredictionError as exc:
        return jsonify({"error": str(exc)}), 400

    return (
        jsonify(
            {
                "prediction": {
                    "id": position.id,
                    "event_id": position.event_id,
                    "outcome_id": position.outcome_id,
                    "stake_amount": str(position.stake_amount),
                    "share_quantity": str(position.share_quantity),
                    "average_price": str(position.average_price),
                    "status": position.status,
                },
                "event": _serialize_event(position.event),
            }
        ),
        201,
    )


@events_bp.post("/events/<int:event_id>/resolve")
@jwt_required()
def resolve_event_endpoint(event_id: int):
    payload = request.get_json(silent=True) or {}
    if payload.get("winning_outcome_id") is None:
        return jsonify({"error": "winning_outcome_id is required."}), 400

    try:
        event = resolve_event(
            event_id=event_id,
            winning_outcome_id=int(payload["winning_outcome_id"]),
            resolver_user_id=int(get_jwt_identity()),
        )
    except EventError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"event": _serialize_event(event)})