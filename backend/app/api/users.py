from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.models.event import Event
from app.models.prediction import PredictionPosition
from app.models.user import User
from app.services.billing_service import get_billing_summary
from app.services.entitlement_service import get_user_entitlements


users_bp = Blueprint("users", __name__)


@users_bp.get("/me")
@jwt_required()
def me():
    user = User.query.filter_by(id=int(get_jwt_identity())).first()
    if user is None:
        return jsonify({"error": "User not found."}), 404

    predictions = (
        PredictionPosition.query.filter_by(user_id=user.id)
        .order_by(PredictionPosition.created_at.desc())
        .limit(20)
        .all()
    )
    created_events = Event.query.filter_by(creator_id=user.id).order_by(Event.created_at.desc()).limit(20).all()
    subscription = get_billing_summary(user.id)
    entitlements = get_user_entitlements(user.id)

    return jsonify(
        {
            "id": user.id,
            "email": user.email,
            "handle": user.handle,
            "is_admin": user.is_admin,
            "email_verified": user.email_verified,
            "verification_status": user.verification_status,
            "wallet": {
                "currency_code": user.wallet.currency_code,
                "current_balance": str(user.wallet.current_balance),
            },
            "subscription": subscription,
            "entitlements": entitlements,
            "account_flags": {
                "failed_login_attempts": user.failed_login_attempts,
                "suspicious_activity": user.suspicious_activity,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            },
            "recent_predictions": [
                {
                    "id": prediction.id,
                    "event_id": prediction.event_id,
                    "event_title": prediction.event.title,
                    "event_status": prediction.event.status,
                    "outcome_id": prediction.outcome_id,
                    "outcome_label": prediction.outcome.label,
                    "stake_amount": str(prediction.stake_amount),
                    "share_quantity": str(prediction.share_quantity),
                    "average_price": str(prediction.average_price),
                    "status": prediction.status,
                    "payout_amount": str(prediction.payout_amount),
                    "created_at": prediction.created_at.isoformat(),
                }
                for prediction in predictions
            ],
            "recent_created_events": [
                {
                    "id": event.id,
                    "title": event.title,
                    "status": event.status,
                    "category": event.category,
                    "closes_at": event.closes_at.isoformat(),
                    "resolves_at": event.resolves_at.isoformat(),
                    "moderation_notes": event.moderation_notes,
                    "moderated_by_user_id": event.moderated_by_user_id,
                }
                for event in created_events
            ],
        }
    )
