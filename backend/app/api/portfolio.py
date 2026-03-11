from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.services.asset_service import AssetError, create_asset, list_assets, update_asset_price
from app.services.asset_service import get_asset_by_symbol
from app.services.market_data_service import MarketDataError, get_market_quote, get_market_quotes, search_market_assets
from app.services.portfolio_service import (
    PortfolioError,
    add_watchlist_symbol,
    create_trade,
    get_private_portfolio,
    get_public_portfolio_summary_by_handle,
    list_watchlist,
    remove_watchlist_symbol,
)
from app.utils.admin import admin_required


portfolio_bp = Blueprint("portfolio", __name__)


def _serialize_asset(asset) -> dict:
    return {
        "id": asset.id,
        "symbol": asset.symbol,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "current_price": str(asset.current_price),
        "is_active": asset.is_active,
    }


@portfolio_bp.get("/assets")
def list_assets_endpoint():
    return jsonify({"items": [_serialize_asset(asset) for asset in list_assets()]})


@portfolio_bp.get("/portfolio/watchlist")
@jwt_required()
def list_watchlist_endpoint():
    items = list_watchlist(int(get_jwt_identity()))
    return jsonify({"items": [_serialize_asset(asset) for asset in items]})


@portfolio_bp.post("/portfolio/watchlist")
@jwt_required()
def add_watchlist_item_endpoint():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol")
    if symbol in (None, ""):
        return jsonify({"error": "symbol is required."}), 400

    try:
        asset = add_watchlist_symbol(int(get_jwt_identity()), str(symbol))
    except PortfolioError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"asset": _serialize_asset(asset)}), 201


@portfolio_bp.delete("/portfolio/watchlist/<string:symbol>")
@jwt_required()
def remove_watchlist_item_endpoint(symbol: str):
    try:
        remove_watchlist_symbol(int(get_jwt_identity()), symbol)
    except PortfolioError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True, "symbol": symbol.strip().upper()})


@portfolio_bp.get("/assets/search")
def search_assets_endpoint():
    query = (request.args.get("q") or "").strip()
    limit = request.args.get("limit", type=int) or 8
    if not query:
        return jsonify({"items": []})

    try:
        items = search_market_assets(query, limit=limit)
    except MarketDataError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception:
        return jsonify({"error": "Market data provider is temporarily unavailable. Try again in a moment."}), 502

    active_assets = {asset.symbol: asset for asset in list_assets()}
    return jsonify(
        {
            "items": [
                {
                    **item,
                    "local_asset_id": active_assets.get(item["symbol"]).id if active_assets.get(item["symbol"]) else None,
                }
                for item in items
            ]
        }
    )


@portfolio_bp.get("/assets/quotes")
def list_market_quotes_endpoint():
    raw_symbols = (request.args.get("symbols") or "").strip()
    if not raw_symbols:
        return jsonify({"items": []})

    symbols = [item.strip().upper() for item in raw_symbols.split(",") if item.strip()]
    try:
        items = get_market_quotes(symbols)
    except Exception:
        return jsonify({"error": "Market data provider is temporarily unavailable. Try again in a moment."}), 502
    active_assets = {asset.symbol: asset for asset in list_assets()}
    return jsonify(
        {
            "items": [
                {
                    **item,
                    "local_asset_id": active_assets.get(item["symbol"]).id if active_assets.get(item["symbol"]) else None,
                }
                for item in items
            ]
        }
    )


@portfolio_bp.get("/assets/<string:symbol>/quote")
def market_quote_endpoint(symbol: str):
    try:
        item = get_market_quote(symbol, track=True)
    except MarketDataError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception:
        return jsonify({"error": "Market data provider is temporarily unavailable. Try again in a moment."}), 502

    local_asset = get_asset_by_symbol(item["symbol"])
    return jsonify({"asset": {**item, "local_asset_id": local_asset.id if local_asset else None}})


@portfolio_bp.post("/assets")
@admin_required
def create_asset_endpoint():
    payload = request.get_json(silent=True) or {}
    required_fields = ["symbol", "name", "asset_type", "current_price"]
    missing_fields = [field for field in required_fields if payload.get(field) in (None, "")]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    try:
        current_price = Decimal(str(payload["current_price"]))
        asset = create_asset(
            symbol=payload["symbol"],
            name=payload["name"],
            asset_type=payload["asset_type"],
            current_price=current_price,
        )
    except (InvalidOperation, AssetError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"asset": _serialize_asset(asset)}), 201


@portfolio_bp.patch("/assets/<int:asset_id>/price")
@admin_required
def update_asset_price_endpoint(asset_id: int):
    payload = request.get_json(silent=True) or {}
    if payload.get("current_price") is None:
        return jsonify({"error": "current_price is required."}), 400

    try:
        asset = update_asset_price(asset_id=asset_id, new_price=Decimal(str(payload["current_price"])))
    except (InvalidOperation, AssetError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"asset": _serialize_asset(asset)})


@portfolio_bp.post("/portfolio/trades")
@jwt_required()
def create_trade_endpoint():
    payload = request.get_json(silent=True) or {}
    if payload.get("side") is None or payload.get("quantity") is None:
        return jsonify({"error": "side and quantity are required."}), 400
    if payload.get("asset_id") is None and payload.get("symbol") in (None, ""):
        return jsonify({"error": "asset_id or symbol is required."}), 400

    try:
        trade = create_trade(
            user_id=int(get_jwt_identity()),
            side=payload["side"],
            quantity=Decimal(str(payload["quantity"])),
            asset_id=int(payload["asset_id"]) if payload.get("asset_id") is not None else None,
            symbol=payload.get("symbol"),
        )
    except (InvalidOperation, PortfolioError) as exc:
        return jsonify({"error": str(exc)}), 400

    return (
        jsonify(
            {
                "trade": {
                    "id": trade.id,
                    "asset_id": trade.asset_id,
                    "symbol": trade.asset.symbol,
                    "side": trade.side,
                    "quantity": str(trade.quantity),
                    "price": str(trade.price),
                    "gross_amount": str(trade.gross_amount),
                }
            }
        ),
        201,
    )


@portfolio_bp.get("/portfolio/me")
@jwt_required()
def my_portfolio_endpoint():
    try:
        portfolio = get_private_portfolio(int(get_jwt_identity()))
    except PortfolioError as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify(portfolio)


@portfolio_bp.get("/users/<string:handle>/portfolio-summary")
def public_portfolio_summary_endpoint(handle: str):
    try:
        summary = get_public_portfolio_summary_by_handle(handle)
    except PortfolioError as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify({"summary": summary})