from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from flask import Blueprint, current_app, jsonify

from app.extensions import db


health_bp = Blueprint("health", __name__)


@health_bp.get("/health/live")
def live():
    return jsonify(
        {
            "status": "ok",
            "service": "prognose-backend",
            "environment": current_app.config.get("ENV", "unknown"),
            "version": current_app.config["APP_VERSION"],
        }
    )


@health_bp.get("/health/ready")
def ready():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return jsonify({"status": "error", "database": "unavailable"}), 503

    return jsonify({"status": "ok", "database": "available"})
