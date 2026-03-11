from app.extensions import db
from app.models.base import BaseModel


class LeaderboardSnapshot(BaseModel):
    __tablename__ = "leaderboard_snapshots"
    __table_args__ = (
        db.UniqueConstraint("leaderboard_type", "season_key", "user_id", name="uq_leaderboard_type_season_user"),
    )

    leaderboard_type = db.Column(db.String(32), nullable=False, index=True)
    season_key = db.Column(db.String(32), nullable=False, default="global", server_default="global", index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    rank = db.Column(db.Integer, nullable=False, index=True)
    score = db.Column(db.Numeric(18, 2), nullable=False)
    metrics = db.Column(db.JSON, nullable=False)
