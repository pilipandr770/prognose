from app.extensions import db
from app.models.base import BaseModel


class FollowRelation(BaseModel):
    __tablename__ = "follows"
    __table_args__ = (db.UniqueConstraint("follower_id", "followee_id", name="uq_follower_followee"),)

    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    followee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)


class SocialNotification(BaseModel):
    __tablename__ = "social_notifications"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    notification_type = db.Column(db.String(32), nullable=False, index=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"), index=True)
    payload = db.Column(db.JSON, nullable=False, default=dict)
