from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.services.billing_service import (
    BillingError,
    create_checkout_session,
    get_billing_summary,
    initialize_billing_catalog,
    list_plans,
    serialize_plan,
    serialize_subscription,
    sync_subscription_from_event,
)


billing_bp = Blueprint("billing", __name__)


@billing_bp.get("/billing/plans")
def list_plans_endpoint():
    initialize_billing_catalog()
    return jsonify({"items": [serialize_plan(plan) for plan in list_plans()]})


@billing_bp.get("/billing/me")
@jwt_required()
def my_billing_endpoint():
    try:
        summary = get_billing_summary(int(get_jwt_identity()))
    except BillingError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"subscription": summary})


@billing_bp.post("/billing/checkout-session")
@jwt_required()
def create_checkout_session_endpoint():
    payload = request.get_json(silent=True) or {}
    plan_code = (payload.get("plan_code") or "").strip().lower()
    if not plan_code:
        return jsonify({"error": "plan_code is required."}), 400

    try:
        session = create_checkout_session(user_id=int(get_jwt_identity()), plan_code=plan_code)
    except BillingError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"checkout_session": session}), 201


@billing_bp.post("/billing/webhooks/stripe")
def stripe_webhook_endpoint():
    payload = request.get_json(silent=True) or {}
    try:
        subscription = sync_subscription_from_event(payload)
    except BillingError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"subscription": serialize_subscription(subscription)})