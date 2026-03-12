from app.extensions import db
from app.models.event import Event
from app.models.asset import Asset
from app.models.event import EventOutcome
from app.models.leaderboard import LeaderboardSnapshot
from app.models.prediction import PredictionPosition
from app.models.social import FollowRelation
from app.models.user import User
from app.services.entitlement_service import get_user_entitlements
from app.services.profile_service import serialize_profile_fields
from app.services.social_notification_service import notify_new_follower
from app.services.portfolio_service import get_public_portfolio_summary_by_handle
from app.services.scoring_service import get_leaderboard, refresh_leaderboard


class SocialError(ValueError):
    pass


def _user_card(user: User, *, current_user_id: int | None = None, reason: str | None = None) -> dict:
    follower_count = FollowRelation.query.filter_by(followee_id=user.id).count()
    following_count = FollowRelation.query.filter_by(follower_id=user.id).count()
    prediction_count = PredictionPosition.query.filter_by(user_id=user.id).count()
    approved_events_count = Event.query.filter(
        Event.creator_id == user.id,
        Event.status.in_(["open", "resolved"]),
    ).count()
    resolved_events_count = Event.query.filter_by(creator_id=user.id, status="resolved").count()

    prediction_rank = LeaderboardSnapshot.query.filter_by(
        leaderboard_type="predictions", season_key="global", user_id=user.id
    ).first()
    portfolio_rank = LeaderboardSnapshot.query.filter_by(
        leaderboard_type="portfolios", season_key="global", user_id=user.id
    ).first()

    is_following = False
    if current_user_id is not None and current_user_id != user.id:
        is_following = FollowRelation.query.filter_by(follower_id=current_user_id, followee_id=user.id).first() is not None

    return {
        "id": user.id,
        "handle": user.handle,
        "display_name": user.display_name,
        "verification_status": user.verification_status,
        "followers_count": follower_count,
        "following_count": following_count,
        "prediction_count": prediction_count,
        "approved_events_count": approved_events_count,
        "resolved_events_count": resolved_events_count,
        "is_following": is_following,
        "is_self": current_user_id == user.id if current_user_id is not None else False,
        "leaderboards": {
            "predictions": {
                "rank": prediction_rank.rank if prediction_rank else None,
                "score": str(prediction_rank.score) if prediction_rank else None,
            },
            "portfolios": {
                "rank": portfolio_rank.rank if portfolio_rank else None,
                "score": str(portfolio_rank.score) if portfolio_rank else None,
            },
        },
        "reason": reason,
    }


def _leaderboard_items(leaderboard_type: str) -> list[dict]:
    items = get_leaderboard(leaderboard_type)
    if not items:
        items = refresh_leaderboard(leaderboard_type)
    return items


def follow_user(*, follower_id: int, followee_handle: str) -> FollowRelation:
    follower = User.query.filter_by(id=follower_id).first()
    followee = User.query.filter_by(handle=followee_handle.strip().lower()).first()

    if follower is None or followee is None:
        raise SocialError("User not found.")
    if follower.id == followee.id:
        raise SocialError("You cannot follow yourself.")

    entitlements = get_user_entitlements(follower.id)
    current_follow_count = FollowRelation.query.filter_by(follower_id=follower.id).count()
    max_follows = int(entitlements.get("max_follows", 0))
    if current_follow_count >= max_follows:
        raise SocialError("Follow limit reached for your current plan.")

    existing_relation = FollowRelation.query.filter_by(follower_id=follower.id, followee_id=followee.id).first()
    if existing_relation:
        return existing_relation

    relation = FollowRelation(follower_id=follower.id, followee_id=followee.id)
    db.session.add(relation)
    notify_new_follower(follower=follower, followee=followee)
    db.session.commit()
    return relation


def unfollow_user(*, follower_id: int, followee_handle: str) -> None:
    followee = User.query.filter_by(handle=followee_handle.strip().lower()).first()
    if followee is None:
        raise SocialError("User not found.")

    relation = FollowRelation.query.filter_by(follower_id=follower_id, followee_id=followee.id).first()
    if relation is None:
        raise SocialError("Follow relation not found.")

    db.session.delete(relation)
    db.session.commit()


def get_public_profile(handle: str) -> dict:
    user = User.query.filter_by(handle=handle.strip().lower()).first()
    if user is None:
        raise SocialError("User not found.")

    follower_count = FollowRelation.query.filter_by(followee_id=user.id).count()
    following_count = FollowRelation.query.filter_by(follower_id=user.id).count()
    prediction_count = PredictionPosition.query.filter_by(user_id=user.id).count()
    approved_events_count = Event.query.filter(
        Event.creator_id == user.id,
        Event.status.in_(["open", "resolved"]),
    ).count()
    resolved_events_count = Event.query.filter_by(creator_id=user.id, status="resolved").count()

    prediction_rank = LeaderboardSnapshot.query.filter_by(
        leaderboard_type="predictions", season_key="global", user_id=user.id
    ).first()
    portfolio_rank = LeaderboardSnapshot.query.filter_by(
        leaderboard_type="portfolios", season_key="global", user_id=user.id
    ).first()

    public_portfolio = get_public_portfolio_summary_by_handle(user.handle)

    return {
        "handle": user.handle,
        "verification_status": user.verification_status,
        "followers_count": follower_count,
        "following_count": following_count,
        "prediction_count": prediction_count,
        "approved_events_count": approved_events_count,
        "resolved_events_count": resolved_events_count,
        "leaderboards": {
            "predictions": {
                "rank": prediction_rank.rank if prediction_rank else None,
                "score": str(prediction_rank.score) if prediction_rank else None,
            },
            "portfolios": {
                "rank": portfolio_rank.rank if portfolio_rank else None,
                "score": str(portfolio_rank.score) if portfolio_rank else None,
            },
        },
        **serialize_profile_fields(user),
        "portfolio_summary": public_portfolio,
    }


def get_activity_feed(user_id: int) -> list[dict]:
    followee_ids = [relation.followee_id for relation in FollowRelation.query.filter_by(follower_id=user_id).all()]
    if not followee_ids:
        return []

    predictions = (
        PredictionPosition.query.filter(PredictionPosition.user_id.in_(followee_ids))
        .order_by(PredictionPosition.created_at.desc())
        .limit(50)
        .all()
    )

    public_events = (
        Event.query.filter(Event.creator_id.in_(followee_ids))
        .filter(Event.status.in_(["open", "resolved"]))
        .order_by(Event.created_at.desc())
        .limit(30)
        .all()
    )

    items = []
    for prediction in predictions:
        author = User.query.filter_by(id=prediction.user_id).first()
        outcome = EventOutcome.query.filter_by(id=prediction.outcome_id).first()
        items.append(
            {
                "type": "prediction",
                "created_at": prediction.created_at.isoformat(),
                "handle": author.handle if author else None,
                "event_id": prediction.event_id,
                "event_title": prediction.event.title,
                "outcome": outcome.label if outcome else None,
                "stake_amount": str(prediction.stake_amount),
                "share_quantity": str(prediction.share_quantity),
                "status": prediction.status,
            }
        )

    for event in public_events:
        author = User.query.filter_by(id=event.creator_id).first()
        items.append(
            {
                "type": "event",
                "created_at": event.created_at.isoformat(),
                "handle": author.handle if author else None,
                "event_id": event.id,
                "event_title": event.title,
                "category": event.category,
                "event_status": event.status,
                "closes_at": event.closes_at.isoformat(),
            }
        )

    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items[:60]


def get_social_discovery(user_id: int) -> dict:
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        raise SocialError("User not found.")

    following_relations = FollowRelation.query.filter_by(follower_id=user_id).all()
    following_ids = {relation.followee_id for relation in following_relations}
    following_users = User.query.filter(User.id.in_(following_ids)).order_by(User.handle.asc()).all() if following_ids else []

    prediction_rows = _leaderboard_items("predictions")
    portfolio_rows = _leaderboard_items("portfolios")

    prediction_leaders = []
    for row in prediction_rows[:5]:
        if row["user_id"] == user_id:
            continue
        leader = User.query.filter_by(id=row["user_id"]).first()
        if leader is None:
            continue
        prediction_leaders.append(_user_card(leader, current_user_id=user_id, reason=f"Prediction rank #{row['rank']}"))

    portfolio_leaders = []
    for row in portfolio_rows[:5]:
        if row["user_id"] == user_id:
            continue
        leader = User.query.filter_by(id=row["user_id"]).first()
        if leader is None:
            continue
        portfolio_leaders.append(_user_card(leader, current_user_id=user_id, reason=f"Portfolio rank #{row['rank']}"))

    candidate_ids: list[int] = []
    for row in prediction_rows + portfolio_rows:
        candidate_user_id = row["user_id"]
        if candidate_user_id == user_id or candidate_user_id in following_ids or candidate_user_id in candidate_ids:
            continue
        candidate_ids.append(candidate_user_id)
        if len(candidate_ids) >= 6:
            break

    if len(candidate_ids) < 6:
        creator_rows = (
            db.session.query(Event.creator_id, db.func.count(Event.id).label("events_count"))
            .filter(Event.status.in_(["open", "resolved"]))
            .group_by(Event.creator_id)
            .order_by(db.desc("events_count"))
            .limit(10)
            .all()
        )
        for creator_row in creator_rows:
            candidate_user_id = int(creator_row.creator_id)
            if candidate_user_id == user_id or candidate_user_id in following_ids or candidate_user_id in candidate_ids:
                continue
            candidate_ids.append(candidate_user_id)
            if len(candidate_ids) >= 6:
                break

    recommended = []
    for candidate_user_id in candidate_ids:
        candidate = User.query.filter_by(id=candidate_user_id).first()
        if candidate is None:
            continue
        recommended.append(_user_card(candidate, current_user_id=user_id, reason="Suggested from leaderboards and creator activity"))

    return {
        "following": [_user_card(followee, current_user_id=user_id, reason="You already follow this user") for followee in following_users],
        "recommended_users": recommended,
        "top_prediction_users": prediction_leaders,
        "top_portfolio_users": portfolio_leaders,
    }