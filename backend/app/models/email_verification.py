from app.extensions import db
from app.models.base import BaseModel


class EmailVerificationToken(BaseModel):
    __tablename__ = "email_verification_tokens"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.String(128), nullable=False, unique=True, index=True)
    status = db.Column(db.String(32), nullable=False, default="pending", server_default="pending", index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
