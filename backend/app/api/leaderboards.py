from flask import Blueprint, jsonify, request

from app.services.scoring_service import LeaderboardError, get_leaderboard, refresh_leaderboard


leaderboards_bp = Blueprint("leaderboards", __name__)


def _should_refresh() -> bool:
    raw_value = (request.args.get("refresh") or "").strip().lower()
    return raw_value in {"1", "true", "yes"}


@leaderboards_bp.get("/leaderboards/predictions")
def predictions_leaderboard_endpoint():
    try:
        items = refresh_leaderboard("predictions") if _should_refresh() else get_leaderboard("predictions")
        if not items:
            items = refresh_leaderboard("predictions")
    except LeaderboardError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"leaderboard_type": "predictions", "season_key": "global", "items": items})


@leaderboards_bp.get("/leaderboards/portfolios")
def portfolios_leaderboard_endpoint():
    try:
        items = refresh_leaderboard("portfolios") if _should_refresh() else get_leaderboard("portfolios")
        if not items:
            items = refresh_leaderboard("portfolios")
    except LeaderboardError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"leaderboard_type": "portfolios", "season_key": "global", "items": items})