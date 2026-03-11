from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.services.social_service import SocialError, follow_user, get_activity_feed, get_public_profile, unfollow_user


social_bp = Blueprint("social", __name__)


@social_bp.post("/users/<string:handle>/follow")
@jwt_required()
def follow_user_endpoint(handle: str):
    try:
        relation = follow_user(follower_id=int(get_jwt_identity()), followee_handle=handle)
    except SocialError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"follow": {"follower_id": relation.follower_id, "followee_id": relation.followee_id}}), 201


@social_bp.delete("/users/<string:handle>/follow")
@jwt_required()
def unfollow_user_endpoint(handle: str):
    try:
        unfollow_user(follower_id=int(get_jwt_identity()), followee_handle=handle)
    except SocialError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"message": "Unfollowed successfully."})


@social_bp.get("/users/<string:handle>")
def public_profile_endpoint(handle: str):
    try:
        profile = get_public_profile(handle)
    except SocialError as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify({"profile": profile})


@social_bp.get("/social/feed")
@jwt_required()
def activity_feed_endpoint():
    return jsonify({"items": get_activity_feed(int(get_jwt_identity()))})