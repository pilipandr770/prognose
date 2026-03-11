from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, jwt_required

from app.services.auth_service import AuthError, authenticate_user, register_user, verify_email_token


auth_bp = Blueprint("auth", __name__)


def _user_payload(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "handle": user.handle,
        "email_verified": user.email_verified,
        "verification_status": user.verification_status,
        "wallet_balance": str(user.wallet.current_balance),
    }


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()
    handle = (payload.get("handle") or "").strip()
    password = payload.get("password") or ""

    if not email or not handle or not password:
        return jsonify({"error": "email, handle and password are required."}), 400

    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters long."}), 400

    try:
        user = register_user(email=email, handle=handle, password=password)
    except AuthError as exc:
        return jsonify({"error": str(exc)}), 409

    response = {
        "message": "Account created successfully.",
        "user": _user_payload(user),
    }

    if current_app.config.get("DEBUG") or current_app.config.get("TESTING"):
        response["dev_notes"] = {"email_verification_token": user.email_verification_token}

    return jsonify(response), 201


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required."}), 400

    try:
        user = authenticate_user(email=email, password=password, ip_address=request.remote_addr)
    except AuthError as exc:
        return jsonify({"error": str(exc)}), 401

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    return jsonify({"access_token": access_token, "refresh_token": refresh_token, "user": _user_payload(user)})


@auth_bp.post("/verify-email")
def verify_email():
    payload = request.get_json(silent=True) or {}
    token = (payload.get("token") or "").strip()
    if not token:
        return jsonify({"error": "token is required."}), 400

    try:
        user = verify_email_token(token)
    except AuthError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"message": "Email verified successfully.", "user": _user_payload(user)})


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    access_token = create_access_token(identity=get_jwt_identity())
    return jsonify({"access_token": access_token})
