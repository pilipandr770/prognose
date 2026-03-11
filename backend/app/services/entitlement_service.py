from app.models.billing import Subscription, SubscriptionPlan


DEFAULT_PLAN_DEFINITIONS = [
    {
        "code": "free",
        "name": "Free",
        "monthly_price": "0.00",
        "currency": "EUR",
        "stripe_price_id": None,
        "sort_order": 1,
        "entitlements": {
            "max_follows": 3,
            "advanced_analytics": False,
            "priority_moderation": False,
            "verified_leaderboard_eligible": False,
        },
    },
    {
        "code": "pro",
        "name": "Pro",
        "monthly_price": "12.00",
        "currency": "EUR",
        "stripe_price_id": "price_pro_placeholder",
        "sort_order": 2,
        "entitlements": {
            "max_follows": 25,
            "advanced_analytics": True,
            "priority_moderation": False,
            "verified_leaderboard_eligible": False,
        },
    },
    {
        "code": "elite",
        "name": "Elite",
        "monthly_price": "29.00",
        "currency": "EUR",
        "stripe_price_id": "price_elite_placeholder",
        "sort_order": 3,
        "entitlements": {
            "max_follows": 250,
            "advanced_analytics": True,
            "priority_moderation": True,
            "verified_leaderboard_eligible": True,
        },
    },
]


def ensure_default_plans(db) -> list[SubscriptionPlan]:
    plans = []
    for definition in DEFAULT_PLAN_DEFINITIONS:
        plan = SubscriptionPlan.query.filter_by(code=definition["code"]).first()
        if plan is None:
            plan = SubscriptionPlan(**definition)
            db.session.add(plan)
        else:
            plan.name = definition["name"]
            plan.monthly_price = definition["monthly_price"]
            plan.currency = definition["currency"]
            plan.stripe_price_id = definition["stripe_price_id"]
            plan.entitlements = definition["entitlements"]
            plan.sort_order = definition["sort_order"]
            plan.is_active = True
        plans.append(plan)

    db.session.flush()
    return plans


def get_plan_by_code(plan_code: str) -> SubscriptionPlan | None:
    return SubscriptionPlan.query.filter_by(code=plan_code.strip().lower(), is_active=True).first()


def get_active_subscription_for_user(user_id: int) -> Subscription | None:
    return (
        Subscription.query.filter_by(user_id=user_id)
        .filter(Subscription.status.in_(["active", "trialing", "past_due"]))
        .order_by(Subscription.created_at.desc())
        .first()
    )


def get_user_entitlements(user_id: int) -> dict:
    subscription = get_active_subscription_for_user(user_id)
    if subscription is None:
        free_plan = get_plan_by_code("free")
        return dict(free_plan.entitlements) if free_plan else {}
    return dict(subscription.plan.entitlements)