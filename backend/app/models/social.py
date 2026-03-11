from app.extensions import db
from app.models.base import BaseModel


class FollowRelation(BaseModel):
    __tablename__ = "follows"
    __table_args__ = (db.UniqueConstraint("follower_id", "followee_id", name="uq_follower_followee"),)

    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    followee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
