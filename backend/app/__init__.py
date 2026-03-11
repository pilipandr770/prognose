from flask import Flask, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

from app.api import register_blueprints
from app.config import get_config
from app.extensions import init_extensions
from app.models import register_models
from app.services.market_data_service import init_market_data
from app.tasks.celery_app import init_celery
from app.web import register_web_routes


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    init_extensions(app)
    register_models()
    register_blueprints(app)
    register_web_routes(app)
    init_celery(app)
    init_market_data(app)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_error):
        return jsonify({"error": "Request payload is too large. Reduce source notes and avoid pasting full page HTML."}), 413

    return app
