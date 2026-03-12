from app.extensions import db
from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    handle = db.Column(db.String(50), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(80), nullable=True)
    bio = db.Column(db.String(500), nullable=True)
    location = db.Column(db.String(80), nullable=True)
    website_url = db.Column(db.String(255), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))
    verification_status = db.Column(db.String(32), nullable=False, default="none", server_default="none")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("true"))
    is_admin = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_ip = db.Column(db.String(64), nullable=True)
    suspicious_activity = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("false"))

    wallet = db.relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
