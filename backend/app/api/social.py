from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.services.social_service import (
    SocialError,
    follow_user,
    get_activity_feed,
    get_public_profile,
    get_social_discovery,
    unfollow_user,
)
from app.services.social_notification_service import (
    SocialNotificationError,
    list_social_notifications,
    mark_all_social_notifications_read,
    mark_social_notification_read,
)


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


@social_bp.get("/social/discovery")
@jwt_required()
def social_discovery_endpoint():
    try:
        payload = get_social_discovery(int(get_jwt_identity()))
    except SocialError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(payload)


@social_bp.get("/social/inbox")
@jwt_required()
def social_inbox_endpoint():
    unread_only = str(request.args.get("unread_only") or "").strip().lower() in {"1", "true", "yes"}
    return jsonify({"items": list_social_notifications(int(get_jwt_identity()), unread_only=unread_only)})


@social_bp.post("/social/inbox/read-all")
@jwt_required()
def social_inbox_read_all_endpoint():
    updated = mark_all_social_notifications_read(int(get_jwt_identity()))
    return jsonify({"updated": updated})


@social_bp.post("/social/inbox/<int:notification_id>/read")
@jwt_required()
def social_inbox_read_endpoint(notification_id: int):
    try:
        notification = mark_social_notification_read(int(get_jwt_identity()), notification_id)
    except SocialNotificationError as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify({"notification": notification})