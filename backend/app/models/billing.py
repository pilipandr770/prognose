from app.extensions import db
from app.models.base import BaseModel


class SubscriptionPlan(BaseModel):
    __tablename__ = "subscription_plans"

    code = db.Column(db.String(32), nullable=False, unique=True, index=True)
    name = db.Column(db.String(64), nullable=False)
    monthly_price = db.Column(db.Numeric(18, 2), nullable=False, server_default="0")
    currency = db.Column(db.String(8), nullable=False, default="EUR", server_default="EUR")
    stripe_price_id = db.Column(db.String(128), nullable=True)
    entitlements = db.Column(db.JSON, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("true"))
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")


class Subscription(BaseModel):
    __tablename__ = "subscriptions"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("subscription_plans.id"), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="active", server_default="active", index=True)
    billing_provider = db.Column(db.String(32), nullable=False, default="internal", server_default="internal")
    provider_customer_id = db.Column(db.String(128), nullable=True, index=True)
    provider_subscription_id = db.Column(db.String(128), nullable=True, index=True)
    current_period_start = db.Column(db.DateTime(timezone=True), nullable=True)
    current_period_end = db.Column(db.DateTime(timezone=True), nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))

    plan = db.relationship("SubscriptionPlan")