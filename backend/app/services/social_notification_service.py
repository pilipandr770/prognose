from app.extensions import db
from app.models.event import Event
from app.models.social import FollowRelation, SocialNotification
from app.models.user import User


class SocialNotificationError(ValueError):
    pass


def create_social_notification(*, user_id: int, notification_type: str, actor_user_id: int | None = None, payload: dict | None = None) -> SocialNotification:
    notification = SocialNotification(
        user_id=user_id,
        actor_user_id=actor_user_id,
        notification_type=notification_type,
        payload=payload or {},
    )
    db.session.add(notification)
    return notification


def notify_new_follower(*, follower: User, followee: User) -> SocialNotification:
    return create_social_notification(
        user_id=followee.id,
        actor_user_id=follower.id,
        notification_type="new_follower",
        payload={
            "follower_handle": follower.handle,
        },
    )


def notify_event_moderated(*, event: Event, decision: str) -> SocialNotification:
    return create_social_notification(
        user_id=event.creator_id,
        actor_user_id=event.moderated_by_user_id,
        notification_type="event_moderated",
        payload={
            "event_id": event.id,
            "event_title": event.title,
            "decision": decision,
            "status": event.status,
            "moderation_notes": event.moderation_notes,
        },
    )


def notify_event_published(event: Event) -> None:
    follower_ids = [relation.follower_id for relation in FollowRelation.query.filter_by(followee_id=event.creator_id).all()]
    for follower_id in follower_ids:
        create_social_notification(
            user_id=follower_id,
            actor_user_id=event.creator_id,
            notification_type="followed_user_event_published",
            payload={
                "event_id": event.id,
                "event_title": event.title,
                "category": event.category,
                "status": event.status,
            },
        )


def _serialize_social_notification(notification: SocialNotification) -> dict:
    actor = User.query.filter_by(id=notification.actor_user_id).first() if notification.actor_user_id else None
    return {
        "id": notification.id,
        "notification_type": notification.notification_type,
        "is_read": notification.is_read,
        "actor_user_id": notification.actor_user_id,
        "actor_handle": actor.handle if actor else None,
        "payload": notification.payload or {},
        "created_at": notification.created_at.isoformat(),
    }


def list_social_notifications(user_id: int, *, unread_only: bool = False, limit: int = 40) -> list[dict]:
    query = SocialNotification.query.filter_by(user_id=user_id)
    if unread_only:
        query = query.filter_by(is_read=False)
    notifications = query.order_by(SocialNotification.created_at.desc()).limit(limit).all()
    return [_serialize_social_notification(notification) for notification in notifications]


def mark_social_notification_read(user_id: int, notification_id: int) -> dict:
    notification = SocialNotification.query.filter_by(id=notification_id, user_id=user_id).first()
    if notification is None:
        raise SocialNotificationError("Notification not found.")

    notification.is_read = True
    db.session.commit()
    return _serialize_social_notification(notification)


def mark_all_social_notifications_read(user_id: int) -> int:
    notifications = SocialNotification.query.filter_by(user_id=user_id, is_read=False).all()
    for notification in notifications:
        notification.is_read = True
    db.session.commit()
    return len(notifications)


def get_unread_social_notifications_count(user_id: int) -> int:
    return SocialNotification.query.filter_by(user_id=user_id, is_read=False).count()
