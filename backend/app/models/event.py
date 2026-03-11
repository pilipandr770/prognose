from app.extensions import db
from app.models.base import BaseModel


class Event(BaseModel):
    __tablename__ = "events"

    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(64), nullable=False, index=True)
    event_type = db.Column(db.String(32), nullable=False, default="binary", server_default="binary")
    status = db.Column(db.String(32), nullable=False, default="open", server_default="open", index=True)
    market_liquidity = db.Column(db.Numeric(18, 2), nullable=False, default="375.00", server_default="375.00")
    source_of_truth = db.Column(db.String(255), nullable=False)
    closes_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    resolves_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    resolved_outcome_id = db.Column(db.Integer, nullable=True, index=True)
    moderation_notes = db.Column(db.Text, nullable=True)
    moderated_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    outcomes = db.relationship(
        "EventOutcome",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventOutcome.position.asc()",
        foreign_keys="EventOutcome.event_id",
        primaryjoin="Event.id == EventOutcome.event_id",
    )
    predictions = db.relationship("PredictionPosition", back_populates="event", cascade="all, delete-orphan")


class EventOutcome(BaseModel):
    __tablename__ = "event_outcomes"

    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    position = db.Column(db.Integer, nullable=False)

    event = db.relationship(
        "Event",
        back_populates="outcomes",
        foreign_keys="EventOutcome.event_id",
        primaryjoin="EventOutcome.event_id == Event.id",
    )
