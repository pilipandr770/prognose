from datetime import datetime, timedelta, timezone
from uuid import uuid4

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.email_verification import EmailVerificationToken
from app.models.user import User
from app.services.billing_service import assign_default_subscription
from app.services.wallet_service import create_wallet_for_user, grant_signup_balance


class AuthError(ValueError):
    pass


FAILED_LOGIN_SUSPICIOUS_THRESHOLD = 5


def _issue_email_verification_token(user_id: int) -> EmailVerificationToken:
    token = EmailVerificationToken(
        user_id=user_id,
        token=uuid4().hex,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.session.add(token)
    db.session.flush()
    return token


def register_user(*, email: str, handle: str, password: str) -> User:
    normalized_email = email.strip().lower()
    normalized_handle = handle.strip().lower()

    if User.query.filter_by(email=normalized_email).first():
        raise AuthError("Email is already registered.")

    if User.query.filter_by(handle=normalized_handle).first():
        raise AuthError("Handle is already taken.")

    should_be_admin = User.query.filter_by(is_admin=True).first() is None

    user = User(
        email=normalized_email,
        handle=normalized_handle,
        password_hash=generate_password_hash(password),
        is_admin=should_be_admin,
    )
    db.session.add(user)
    db.session.flush()

    wallet = create_wallet_for_user(user.id)
    grant_signup_balance(wallet.id)
    assign_default_subscription(user.id)
    verification_token = _issue_email_verification_token(user.id)
    db.session.commit()

    user.email_verification_token = verification_token.token

    return user


def authenticate_user(*, email: str, password: str, ip_address: str | None = None) -> User:
    user = User.query.filter_by(email=email.strip().lower()).first()

    if user is None:
        raise AuthError("Invalid credentials.")

    if not check_password_hash(user.password_hash, password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= FAILED_LOGIN_SUSPICIOUS_THRESHOLD:
            user.suspicious_activity = True
        db.session.commit()
        raise AuthError("Invalid credentials.")

    if not user.is_active:
        raise AuthError("Account is inactive.")

    user.failed_login_attempts = 0
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = ip_address
    db.session.commit()

    return user


def verify_email_token(token_value: str) -> User:
    verification_token = EmailVerificationToken.query.filter_by(token=token_value, status="pending").first()
    if verification_token is None:
        raise AuthError("Verification token is invalid.")

    expires_at = verification_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        verification_token.status = "expired"
        db.session.commit()
        raise AuthError("Verification token has expired.")

    user = User.query.filter_by(id=verification_token.user_id).first()
    if user is None:
        raise AuthError("User not found.")

    verification_token.status = "used"
    verification_token.used_at = datetime.now(timezone.utc)
    user.email_verified = True
    user.verification_status = "email_verified"
    db.session.commit()
    return user
