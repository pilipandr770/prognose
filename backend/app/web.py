from pathlib import Path

from flask import Flask, send_from_directory


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"
PAGE_MAP = {
    "dashboard": "dashboard.html",
    "login": "login.html",
    "register": "register.html",
    "events": "events.html",
    "portfolio": "portfolio.html",
    "leaderboards": "leaderboards.html",
    "social": "social.html",
    "billing": "billing.html",
    "admin": "admin.html",
}


def register_web_routes(app: Flask) -> None:
    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<string:page>")
    def page(page: str):
        filename = PAGE_MAP.get(page)
        if filename is None:
            return send_from_directory(FRONTEND_DIR, "index.html")
        return send_from_directory(FRONTEND_DIR, filename)

    @app.get("/assets/<path:filename>")
    def assets(filename: str):
        return send_from_directory(ASSETS_DIR, filename)