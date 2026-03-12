from decimal import Decimal, ROUND_HALF_UP

from app.extensions import db
from app.models.leaderboard import LeaderboardSnapshot
from app.models.prediction import PredictionPosition
from app.models.social import FollowRelation
from app.models.user import User
from app.services.portfolio_service import get_private_portfolio


SCORE_PLACES = Decimal("0.01")
SEASON_KEY = "global"


class LeaderboardError(ValueError):
    pass


def _quantize_score(value: Decimal) -> Decimal:
    return Decimal(value).quantize(SCORE_PLACES, rounding=ROUND_HALF_UP)


def _compute_prediction_rows() -> list[dict]:
    rows = []
    users = User.query.filter_by(is_active=True).order_by(User.handle.asc()).all()

    for user in users:
        resolved_positions = (
            PredictionPosition.query.filter_by(user_id=user.id)
            .filter(PredictionPosition.status.in_(["won", "lost"]))
            .all()
        )
        if not resolved_positions:
            continue

        resolved_count = len(resolved_positions)
        wins = sum(1 for position in resolved_positions if position.status == "won")
        losses = resolved_count - wins
        total_staked = sum(Decimal(position.stake_amount) for position in resolved_positions)
        total_payout = sum(Decimal(position.payout_amount or 0) for position in resolved_positions)
        profit = total_payout - total_staked
        accuracy_pct = (Decimal(wins) / Decimal(resolved_count)) * Decimal("100")
        roi_pct = Decimal("0.00")
        if total_staked > Decimal("0.00"):
            roi_pct = (profit / total_staked) * Decimal("100")

        sample_bonus = min(Decimal(resolved_count) * Decimal("2.50"), Decimal("25.00"))
        score = _quantize_score(accuracy_pct + (roi_pct * Decimal("0.60")) + sample_bonus)

        rows.append(
            {
                "user_id": user.id,
                "handle": user.handle,
                "score": score,
                "sort_score": score,
                "metrics": {
                    "wins": wins,
                    "losses": losses,
                    "resolved_predictions": resolved_count,
                    "accuracy_pct": str(_quantize_score(accuracy_pct)),
                    "roi_pct": str(_quantize_score(roi_pct)),
                    "profit": str(_quantize_score(profit)),
                    "total_staked": str(_quantize_score(total_staked)),
                },
            }
        )

    rows.sort(
        key=lambda row: (
            row["sort_score"],
            Decimal(row["metrics"]["profit"]),
            row["metrics"]["resolved_predictions"],
            row["handle"],
        ),
        reverse=True,
    )
    return rows


def _compute_portfolio_rows() -> list[dict]:
    rows = []
    users = User.query.filter_by(is_active=True).order_by(User.handle.asc()).all()

    for user in users:
        portfolio = get_private_portfolio(user.id)
        summary = portfolio["summary"]
        open_positions = int(summary["open_positions_count"])
        total_portfolio_pnl = Decimal(summary["total_portfolio_pnl"])

        if open_positions <= 0 and total_portfolio_pnl == Decimal("0.00"):
            continue

        return_pct = Decimal(summary["return_pct"])
        diversification_bonus = min(Decimal(open_positions) * Decimal("0.50"), Decimal("5.00"))
        score = _quantize_score(return_pct + diversification_bonus)

        rows.append(
            {
                "user_id": user.id,
                "handle": user.handle,
                "score": score,
                "sort_score": score,
                "metrics": {
                    "return_pct": str(_quantize_score(return_pct)),
                    "total_portfolio_pnl": str(_quantize_score(total_portfolio_pnl)),
                    "market_value": summary["market_value"],
                    "open_positions_count": open_positions,
                    "diversification_bonus": str(_quantize_score(diversification_bonus)),
                },
            }
        )

    rows.sort(
        key=lambda row: (
            row["sort_score"],
            Decimal(row["metrics"]["total_portfolio_pnl"]),
            row["metrics"]["open_positions_count"],
            row["handle"],
        ),
        reverse=True,
    )
    return rows


def _persist_rows(leaderboard_type: str, rows: list[dict]) -> None:
    LeaderboardSnapshot.query.filter_by(leaderboard_type=leaderboard_type, season_key=SEASON_KEY).delete()

    for index, row in enumerate(rows, start=1):
        db.session.add(
            LeaderboardSnapshot(
                leaderboard_type=leaderboard_type,
                season_key=SEASON_KEY,
                user_id=row["user_id"],
                rank=index,
                score=row["score"],
                metrics=row["metrics"],
            )
        )

    db.session.commit()


def refresh_leaderboard(leaderboard_type: str) -> list[dict]:
    if leaderboard_type == "predictions":
        rows = _compute_prediction_rows()
    elif leaderboard_type == "portfolios":
        rows = _compute_portfolio_rows()
    else:
        raise LeaderboardError("Unsupported leaderboard type.")

    _persist_rows(leaderboard_type, rows)
    return get_leaderboard(leaderboard_type)


def get_leaderboard(leaderboard_type: str) -> list[dict]:
    snapshots = (
        LeaderboardSnapshot.query.filter_by(leaderboard_type=leaderboard_type, season_key=SEASON_KEY)
        .join(User, LeaderboardSnapshot.user_id == User.id)
        .order_by(LeaderboardSnapshot.rank.asc())
        .all()
    )

    if not snapshots:
        return []

    items = []
    for snapshot in snapshots:
        user = User.query.filter_by(id=snapshot.user_id).first()
        follower_count = FollowRelation.query.filter_by(followee_id=snapshot.user_id).count()
        items.append(
            {
                "user_id": snapshot.user_id,
                "handle": user.handle if user else None,
                "display_name": user.display_name if user else None,
                "bio": user.bio if user else None,
                "followers_count": follower_count,
                "rank": snapshot.rank,
                "score": str(_quantize_score(Decimal(snapshot.score))),
                "metrics": snapshot.metrics,
            }
        )

    return items