from app.extensions import db
from app.models.asset import Asset
from app.models.event import EventOutcome
from app.models.leaderboard import LeaderboardSnapshot
from app.models.prediction import PredictionPosition
from app.models.social import FollowRelation
from app.models.user import User
from app.services.entitlement_service import get_user_entitlements
from app.services.portfolio_service import get_public_portfolio_summary_by_handle


class SocialError(ValueError):
    pass


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
                "outcome": outcome.label if outcome else None,
                "stake_amount": str(prediction.stake_amount),
                "share_quantity": str(prediction.share_quantity),
                "status": prediction.status,
            }
        )

    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items