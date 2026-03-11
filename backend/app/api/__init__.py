from flask import Flask

from app.api.admin import admin_bp
from app.api.auth import auth_bp
from app.api.billing import billing_bp
from app.api.events import events_bp
from app.api.health import health_bp
from app.api.leaderboards import leaderboards_bp
from app.api.portfolio import portfolio_bp
from app.api.social import social_bp
from app.api.users import users_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(billing_bp, url_prefix="/api")
    app.register_blueprint(events_bp, url_prefix="/api")
    app.register_blueprint(leaderboards_bp, url_prefix="/api")
    app.register_blueprint(portfolio_bp, url_prefix="/api")
    app.register_blueprint(social_bp, url_prefix="/api")
    app.register_blueprint(users_bp, url_prefix="/api")
