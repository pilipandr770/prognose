from datetime import datetime, timezone
from uuid import uuid4

from flask import current_app

from app.extensions import db
from app.models.billing import Subscription, SubscriptionPlan
from app.models.user import User
from app.services.entitlement_service import ensure_default_plans, get_active_subscription_for_user, get_plan_by_code


class BillingError(ValueError):
    pass


def initialize_billing_catalog() -> None:
    ensure_default_plans(db)
    db.session.commit()


def assign_default_subscription(user_id: int) -> Subscription:
    ensure_default_plans(db)
    existing_subscription = get_active_subscription_for_user(user_id)
    if existing_subscription:
        return existing_subscription

    free_plan = get_plan_by_code("free")
    if free_plan is None:
        raise BillingError("Free plan is not configured.")

    subscription = Subscription(
        user_id=user_id,
        plan_id=free_plan.id,
        status="active",
        billing_provider="internal",
        current_period_start=datetime.now(timezone.utc),
    )
    db.session.add(subscription)
    db.session.flush()
    return subscription


def serialize_plan(plan: SubscriptionPlan) -> dict:
    return {
        "code": plan.code,
        "name": plan.name,
        "monthly_price": str(plan.monthly_price),
        "currency": plan.currency,
        "entitlements": plan.entitlements,
    }


def serialize_subscription(subscription: Subscription) -> dict:
    return {
        "plan": serialize_plan(subscription.plan),
        "status": subscription.status,
        "billing_provider": subscription.billing_provider,
        "provider_customer_id": subscription.provider_customer_id,
        "provider_subscription_id": subscription.provider_subscription_id,
        "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
        "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        "cancel_at_period_end": subscription.cancel_at_period_end,
    }


def list_plans() -> list[SubscriptionPlan]:
    ensure_default_plans(db)
    db.session.commit()
    return SubscriptionPlan.query.filter_by(is_active=True).order_by(SubscriptionPlan.sort_order.asc()).all()


def get_billing_summary(user_id: int) -> dict:
    ensure_default_plans(db)
    db.session.commit()

    subscription = get_active_subscription_for_user(user_id)
    if subscription is None:
        subscription = assign_default_subscription(user_id)
        db.session.commit()

    return serialize_subscription(subscription)


def create_checkout_session(*, user_id: int, plan_code: str) -> dict:
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        raise BillingError("User not found.")

    plan = get_plan_by_code(plan_code)
    if plan is None:
        raise BillingError("Plan not found.")
    if plan.code == "free":
        raise BillingError("Free plan does not require checkout.")

    stripe_secret_key = current_app.config.get("STRIPE_SECRET_KEY", "")
    stripe_price_id = (plan.stripe_price_id or "").strip()
    has_live_stripe_price = bool(stripe_price_id) and "placeholder" not in stripe_price_id.lower()
    session_id = f"cs_test_{uuid4().hex}"
    checkout_url = f"{current_app.config['STRIPE_SUCCESS_URL']}?session_id={session_id}&plan={plan.code}"

    if stripe_secret_key and has_live_stripe_price:
        try:
            import stripe

            stripe.api_key = stripe_secret_key
            session = stripe.checkout.Session.create(
                mode="subscription",
                success_url=current_app.config["STRIPE_SUCCESS_URL"] + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=current_app.config["STRIPE_CANCEL_URL"],
                line_items=[{"price": stripe_price_id, "quantity": 1}],
                customer_email=user.email,
                metadata={"user_id": str(user.id), "plan_code": plan.code},
            )
            session_id = session.id
            checkout_url = session.url
        except Exception as exc:  # pragma: no cover
            raise BillingError(f"Stripe checkout error: {exc}") from exc

    return {
        "session_id": session_id,
        "url": checkout_url,
        "mode": "subscription",
        "plan_code": plan.code,
        "provider": "stripe" if stripe_secret_key and has_live_stripe_price else "mock",
    }


def sync_subscription_from_event(payload: dict) -> Subscription:
    ensure_default_plans(db)
    event_type = payload.get("type")
    event_object = ((payload.get("data") or {}).get("object") or {})
    metadata = event_object.get("metadata") or {}

    user_id = metadata.get("user_id") or payload.get("user_id")
    plan_code = metadata.get("plan_code") or payload.get("plan_code")
    if not user_id or not plan_code:
        raise BillingError("Webhook payload must contain user_id and plan_code metadata.")

    user = User.query.filter_by(id=int(user_id)).first()
    if user is None:
        raise BillingError("User not found.")

    plan = get_plan_by_code(str(plan_code))
    if plan is None:
        raise BillingError("Plan not found.")

    subscription = get_active_subscription_for_user(user.id)
    if subscription is None:
        subscription = Subscription(user_id=user.id, plan_id=plan.id)
        db.session.add(subscription)

    status_map = {
        "checkout.session.completed": "active",
        "customer.subscription.updated": event_object.get("status", "active"),
        "customer.subscription.deleted": "canceled",
        "subscription.updated": payload.get("status", "active"),
    }
    subscription.plan_id = plan.id
    subscription.billing_provider = "stripe"
    subscription.status = status_map.get(event_type, payload.get("status", "active"))
    subscription.provider_customer_id = event_object.get("customer") or payload.get("provider_customer_id")
    subscription.provider_subscription_id = event_object.get("subscription") or payload.get("provider_subscription_id")
    subscription.cancel_at_period_end = bool(event_object.get("cancel_at_period_end", False))
    subscription.current_period_start = datetime.now(timezone.utc)
    subscription.current_period_end = None
    db.session.commit()
    return subscription