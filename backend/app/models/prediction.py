from app.extensions import db
from app.models.base import BaseModel


class PredictionPosition(BaseModel):
    __tablename__ = "prediction_positions"
    __table_args__ = (db.UniqueConstraint("user_id", "event_id", name="uq_prediction_user_event"),)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    outcome_id = db.Column(db.Integer, db.ForeignKey("event_outcomes.id"), nullable=False, index=True)
    stake_amount = db.Column(db.Numeric(18, 2), nullable=False)
    share_quantity = db.Column(db.Numeric(18, 6), nullable=False, default="0", server_default="0")
    average_price = db.Column(db.Numeric(18, 6), nullable=False, default="0", server_default="0")
    status = db.Column(db.String(32), nullable=False, default="open", server_default="open")
    payout_amount = db.Column(db.Numeric(18, 2), nullable=True)

    event = db.relationship("Event", back_populates="predictions")
    outcome = db.relationship("EventOutcome")
