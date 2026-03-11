from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from app.extensions import db
from app.models.asset import Asset
from app.models.billing import Subscription
from app.models.event import Event
from app.models.user import User
from app.services.ai_generation_service import AIEventGenerationError, generate_ai_event_batch
from app.services.asset_service import AssetError, create_asset, update_asset_price
from app.services.event_service import EventError, list_pending_events, moderate_event, resolve_event
from app.services.wallet_service import admin_credit_wallet
from app.utils.admin import admin_required


admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/admin/dashboard")
@admin_required
def admin_dashboard():
    return jsonify(
        {
            "users_total": User.query.count(),
            "admins_total": User.query.filter_by(is_admin=True).count(),
            "suspicious_users": User.query.filter_by(suspicious_activity=True).count(),
            "events_total": Event.query.count(),
            "pending_events": Event.query.filter_by(status="pending_review").count(),
            "open_events": Event.query.filter_by(status="open").count(),
            "resolved_events": Event.query.filter_by(status="resolved").count(),
            "assets_total": Asset.query.count(),
            "subscriptions_total": Subscription.query.count(),
        }
    )


@admin_bp.get("/admin/users")
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify(
        {
            "items": [
                {
                    "id": user.id,
                    "email": user.email,
                    "handle": user.handle,
                    "is_admin": user.is_admin,
                    "email_verified": user.email_verified,
                    "verification_status": user.verification_status,
                    "suspicious_activity": user.suspicious_activity,
                    "failed_login_attempts": user.failed_login_attempts,
                    "wallet_balance": str(user.wallet.current_balance) if user.wallet is not None else None,
                }
                for user in users
            ]
        }
    )


@admin_bp.post("/admin/users/<int:user_id>/wallet-credit")
@admin_required
def admin_credit_user_wallet(user_id: int):
    payload = request.get_json(silent=True) or {}
    if payload.get("amount") is None:
        return jsonify({"error": "amount is required."}), 400

    target_user = User.query.filter_by(id=user_id).first()
    if target_user is None or target_user.wallet is None:
        return jsonify({"error": "User wallet not found."}), 404

    admin_user = User.query.filter_by(id=int(get_jwt_identity()), is_admin=True).first()

    try:
        entry = admin_credit_wallet(
            wallet_id=target_user.wallet.id,
            amount=Decimal(str(payload.get("amount"))),
            admin_user_id=admin_user.id,
            note=str(payload.get("note") or "").strip() or None,
        )
        db.session.commit()
    except (InvalidOperation, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "user": {
                "id": target_user.id,
                "handle": target_user.handle,
                "wallet_balance": str(target_user.wallet.current_balance),
            },
            "wallet_entry": {
                "id": entry.id,
                "amount": str(entry.amount),
                "reason_code": entry.reason_code,
                "reference_type": entry.reference_type,
                "reference_id": entry.reference_id,
            },
        }
    )


@admin_bp.get("/admin/events")
@admin_required
def admin_events():
    events = Event.query.order_by(Event.created_at.desc()).all()
    return jsonify(
        {
            "items": [
                {
                    "id": event.id,
                    "title": event.title,
                    "category": event.category,
                    "status": event.status,
                    "creator_id": event.creator_id,
                    "closes_at": event.closes_at.isoformat(),
                    "resolves_at": event.resolves_at.isoformat(),
                    "resolved_outcome_id": event.resolved_outcome_id,
                    "outcomes": [
                        {"id": outcome.id, "label": outcome.label, "position": outcome.position}
                        for outcome in event.outcomes
                    ],
                }
                for event in events
            ]
        }
    )


@admin_bp.get("/admin/events/pending")
@admin_required
def admin_pending_events():
    events = list_pending_events()
    return jsonify(
        {
            "items": [
                {
                    "id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "category": event.category,
                    "status": event.status,
                    "creator_id": event.creator_id,
                    "source_of_truth": event.source_of_truth,
                    "closes_at": event.closes_at.isoformat(),
                    "resolves_at": event.resolves_at.isoformat(),
                    "outcomes": [
                        {"id": outcome.id, "label": outcome.label, "position": outcome.position}
                        for outcome in event.outcomes
                    ],
                }
                for event in events
            ]
        }
    )


@admin_bp.post("/admin/events/<int:event_id>/moderate")
@admin_required
def admin_moderate_event(event_id: int):
    payload = request.get_json(silent=True) or {}
    decision = payload.get("decision")
    if not decision:
        return jsonify({"error": "decision is required."}), 400

    admin_user = User.query.filter_by(id=int(get_jwt_identity()), is_admin=True).first()

    try:
        event = moderate_event(
            event_id=event_id,
            admin_user_id=admin_user.id,
            decision=decision,
            notes=payload.get("notes"),
        )
    except EventError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "event": {
                "id": event.id,
                "title": event.title,
                "status": event.status,
                "moderation_notes": event.moderation_notes,
                "moderated_by_user_id": event.moderated_by_user_id,
            }
        }
    )


@admin_bp.post("/admin/assets")
@admin_required
def admin_create_asset():
    payload = request.get_json(silent=True) or {}
    required_fields = ["symbol", "name", "asset_type", "current_price"]
    missing_fields = [field for field in required_fields if payload.get(field) in (None, "")]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    try:
        asset = create_asset(
            symbol=payload["symbol"],
            name=payload["name"],
            asset_type=payload["asset_type"],
            current_price=Decimal(str(payload["current_price"])),
        )
    except (InvalidOperation, AssetError) as exc:
        return jsonify({"error": str(exc)}), 400

    return (
        jsonify(
            {
                "asset": {
                    "id": asset.id,
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "asset_type": asset.asset_type,
                    "current_price": str(asset.current_price),
                }
            }
        ),
        201,
    )


@admin_bp.patch("/admin/assets/<int:asset_id>/price")
@admin_required
def admin_patch_asset_price(asset_id: int):
    payload = request.get_json(silent=True) or {}
    if payload.get("current_price") is None:
        return jsonify({"error": "current_price is required."}), 400

    try:
        asset = update_asset_price(asset_id=asset_id, new_price=Decimal(str(payload["current_price"])))
    except (InvalidOperation, AssetError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"asset": {"id": asset.id, "symbol": asset.symbol, "current_price": str(asset.current_price)}})


@admin_bp.post("/admin/events/<int:event_id>/resolve")
@admin_required
def admin_resolve_event(event_id: int):
    payload = request.get_json(silent=True) or {}
    if payload.get("winning_outcome_id") is None:
        return jsonify({"error": "winning_outcome_id is required."}), 400

    try:
        admin_user = User.query.filter_by(id=int(get_jwt_identity()), is_admin=True).first()
        event = resolve_event(
            event_id=event_id,
            winning_outcome_id=int(payload["winning_outcome_id"]),
            resolver_user_id=admin_user.id,
            force_admin=True,
        )
    except EventError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"event": {"id": event.id, "status": event.status, "resolved_outcome_id": event.resolved_outcome_id}})


@admin_bp.post("/admin/ai/generate-events")
@admin_required
def admin_generate_ai_events():
    payload = request.get_json(silent=True) or {}

    source_urls = payload.get("source_urls") or []
    if isinstance(source_urls, str):
        source_urls = [line.strip() for line in source_urls.splitlines() if line.strip()]

    source_notes = payload.get("source_notes") or []
    if isinstance(source_notes, str):
        source_notes = [line.strip() for line in source_notes.splitlines() if line.strip()]

    try:
        result = generate_ai_event_batch(
            admin_user_id=int(get_jwt_identity()),
            topics=str(payload.get("topics") or "").strip(),
            count=int(payload.get("count") or 3),
            source_urls=source_urls,
            source_notes=source_notes,
            publish_generated=bool(payload.get("publish_generated")),
            create_seed_predictions=bool(payload.get("create_seed_predictions")),
        )
    except (ValueError, AIEventGenerationError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result)