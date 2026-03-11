from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from app.extensions import db
from app.models.asset import Asset
from app.models.portfolio import PortfolioPosition, PortfolioTrade, PortfolioWatchlistItem
from app.models.user import User
from app.services.asset_service import get_asset_by_symbol, sync_market_asset
from app.services.market_data_service import MarketDataError, get_market_quote
from app.services.wallet_service import create_wallet_entry


STARTING_PORTFOLIO_REFERENCE = Decimal("10000.00")
PRICE_PLACES = Decimal("0.01")
QUANTITY_PLACES = Decimal("0.00000001")


class PortfolioError(ValueError):
    pass


def _quantize_price(value: Decimal) -> Decimal:
    return Decimal(value).quantize(PRICE_PLACES, rounding=ROUND_HALF_UP)


def _quantize_quantity(value: Decimal) -> Decimal:
    return Decimal(value).quantize(QUANTITY_PLACES, rounding=ROUND_HALF_UP)


def _refresh_asset_from_market(asset: Asset) -> Asset:
    try:
        market_quote = get_market_quote(asset.symbol, track=True)
    except MarketDataError:
        return asset

    return sync_market_asset(
        symbol=asset.symbol,
        name=market_quote["name"],
        asset_type=market_quote["asset_type"],
        current_price=Decimal(str(market_quote["current_price"])),
        source=market_quote.get("source") or "yahoo_chart",
        commit=False,
    )


def _load_tradable_asset(*, asset_id: int | None = None, symbol: str | None = None) -> Asset:
    if asset_id is not None:
        asset = Asset.query.filter_by(id=asset_id, is_active=True).first()
        if asset is None:
            raise PortfolioError("Asset not found.")
        return asset

    normalized_symbol = str(symbol or "").strip().upper()
    if not normalized_symbol:
        raise PortfolioError("asset_id or symbol is required.")

    existing_asset = get_asset_by_symbol(normalized_symbol)
    try:
        market_quote = get_market_quote(normalized_symbol, track=True)
    except MarketDataError as exc:
        if existing_asset is not None and existing_asset.is_active:
            return existing_asset
        raise PortfolioError(str(exc)) from exc
    except Exception as exc:
        if existing_asset is not None and existing_asset.is_active:
            return existing_asset
        raise PortfolioError("Market data provider is temporarily unavailable. Try again in a moment.") from exc

    return sync_market_asset(
        symbol=normalized_symbol,
        name=market_quote["name"],
        asset_type=market_quote["asset_type"],
        current_price=Decimal(str(market_quote["current_price"])),
        source=market_quote.get("source") or "yahoo_chart",
        commit=False,
    )


def create_trade(*, user_id: int, side: str, quantity: Decimal, asset_id: int | None = None, symbol: str | None = None) -> PortfolioTrade:
    normalized_side = side.strip().lower()
    normalized_quantity = _quantize_quantity(quantity)
    if normalized_side not in {"buy", "sell"}:
        raise PortfolioError("Trade side must be buy or sell.")
    if normalized_quantity <= Decimal("0"):
        raise PortfolioError("Quantity must be greater than zero.")

    user = User.query.filter_by(id=user_id).first()
    if user is None or user.wallet is None:
        raise PortfolioError("User wallet not found.")

    asset = _load_tradable_asset(asset_id=asset_id, symbol=symbol)

    current_price = _quantize_price(Decimal(asset.current_price))
    gross_amount = _quantize_price(current_price * normalized_quantity)
    position = PortfolioPosition.query.filter_by(user_id=user_id, asset_id=asset.id).first()

    if normalized_side == "buy":
        if position is None:
            position = PortfolioPosition(user_id=user_id, asset_id=asset.id)
            db.session.add(position)
            db.session.flush()

        current_quantity = Decimal(position.quantity)
        current_average_cost = Decimal(position.average_cost)
        new_quantity = current_quantity + normalized_quantity
        total_cost_basis = (current_quantity * current_average_cost) + gross_amount
        position.quantity = new_quantity
        position.average_cost = _quantize_price(total_cost_basis / new_quantity)

        try:
            create_wallet_entry(
                wallet_id=user.wallet.id,
                entry_type="debit",
                amount=gross_amount,
                reason_code="portfolio_buy",
                idempotency_key=f"portfolio-buy:{uuid4()}",
                reference_type="asset",
                reference_id=str(asset.id),
            )
        except ValueError as exc:
            raise PortfolioError(str(exc)) from exc
    else:
        if position is None or Decimal(position.quantity) < normalized_quantity:
            raise PortfolioError("Insufficient asset quantity to sell.")

        cost_basis_sold = _quantize_price(Decimal(position.average_cost) * normalized_quantity)
        realized_pnl = _quantize_price(gross_amount - cost_basis_sold)
        remaining_quantity = Decimal(position.quantity) - normalized_quantity

        create_wallet_entry(
            wallet_id=user.wallet.id,
            entry_type="credit",
            amount=gross_amount,
            reason_code="portfolio_sell",
            idempotency_key=f"portfolio-sell:{uuid4()}",
            reference_type="asset",
            reference_id=str(asset.id),
        )

        position.quantity = remaining_quantity
        position.realized_pnl = _quantize_price(Decimal(position.realized_pnl) + realized_pnl)
        if remaining_quantity == Decimal("0"):
            position.average_cost = Decimal("0.00")

    db.session.flush()
    trade = PortfolioTrade(
        user_id=user_id,
        asset_id=asset.id,
        position_id=position.id,
        side=normalized_side,
        quantity=normalized_quantity,
        price=current_price,
        gross_amount=gross_amount,
    )
    db.session.add(trade)
    db.session.commit()
    return trade


def _portfolio_positions(user_id: int) -> list[PortfolioPosition]:
    return (
        PortfolioPosition.query.filter_by(user_id=user_id)
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .order_by(Asset.symbol.asc())
        .all()
    )


def _ensure_user_exists(user_id: int) -> User:
    user = User.query.filter_by(id=user_id).first()
    if user is None:
        raise PortfolioError("User not found.")
    return user


def list_watchlist(user_id: int) -> list[Asset]:
    _ensure_user_exists(user_id)
    items = (
        PortfolioWatchlistItem.query.filter_by(user_id=user_id)
        .join(Asset, PortfolioWatchlistItem.asset_id == Asset.id)
        .order_by(PortfolioWatchlistItem.created_at.desc())
        .all()
    )
    return [item.asset for item in items if item.asset is not None and item.asset.is_active]


def add_watchlist_symbol(user_id: int, symbol: str) -> Asset:
    _ensure_user_exists(user_id)
    asset = _load_tradable_asset(symbol=symbol)

    existing_item = PortfolioWatchlistItem.query.filter_by(user_id=user_id, asset_id=asset.id).first()
    if existing_item is None:
        db.session.add(PortfolioWatchlistItem(user_id=user_id, asset_id=asset.id))
        db.session.commit()
    else:
        db.session.commit()
    return asset


def remove_watchlist_symbol(user_id: int, symbol: str) -> None:
    _ensure_user_exists(user_id)
    normalized_symbol = str(symbol or "").strip().upper()
    if not normalized_symbol:
        raise PortfolioError("Asset symbol is required.")

    asset = get_asset_by_symbol(normalized_symbol)
    if asset is None:
        return

    item = PortfolioWatchlistItem.query.filter_by(user_id=user_id, asset_id=asset.id).first()
    if item is None:
        return

    db.session.delete(item)
    db.session.commit()


def get_private_portfolio(user_id: int) -> dict:
    user = User.query.filter_by(id=user_id).first()
    if user is None or user.wallet is None:
        raise PortfolioError("User wallet not found.")

    positions = _portfolio_positions(user_id)
    holdings = []
    total_market_value = Decimal("0.00")
    total_cost_basis = Decimal("0.00")
    total_realized_pnl = Decimal("0.00")

    for position in positions:
        quantity = Decimal(position.quantity)
        if quantity <= Decimal("0"):
            continue

        current_price = _quantize_price(Decimal(position.asset.current_price))
        cost_basis = _quantize_price(quantity * Decimal(position.average_cost))
        market_value = _quantize_price(quantity * current_price)
        unrealized_pnl = _quantize_price(market_value - cost_basis)
        total_market_value += market_value
        total_cost_basis += cost_basis
        total_realized_pnl += Decimal(position.realized_pnl)

        holdings.append(
            {
                "asset_id": position.asset.id,
                "symbol": position.asset.symbol,
                "name": position.asset.name,
                "asset_type": position.asset.asset_type,
                "quantity": str(quantity),
                "average_cost": str(_quantize_price(Decimal(position.average_cost))),
                "current_price": str(current_price),
                "cost_basis": str(cost_basis),
                "market_value": str(market_value),
                "unrealized_pnl": str(unrealized_pnl),
            }
        )

    total_market_value = _quantize_price(total_market_value)
    total_cost_basis = _quantize_price(total_cost_basis)
    total_realized_pnl = _quantize_price(total_realized_pnl)
    total_unrealized_pnl = _quantize_price(total_market_value - total_cost_basis)
    total_portfolio_pnl = _quantize_price(total_realized_pnl + total_unrealized_pnl)
    return_pct = Decimal("0.00")
    if total_cost_basis > Decimal("0.00"):
        return_pct = _quantize_price((total_portfolio_pnl / total_cost_basis) * Decimal("100"))

    recent_trades = (
        PortfolioTrade.query.filter_by(user_id=user_id)
        .join(Asset, PortfolioTrade.asset_id == Asset.id)
        .order_by(PortfolioTrade.created_at.desc())
        .limit(20)
        .all()
    )

    return {
        "summary": {
            "market_value": str(total_market_value),
            "cost_basis": str(total_cost_basis),
            "unrealized_pnl": str(total_unrealized_pnl),
            "realized_pnl": str(total_realized_pnl),
            "total_portfolio_pnl": str(total_portfolio_pnl),
            "return_pct": str(return_pct),
            "open_positions_count": len(holdings),
            "available_cash": str(_quantize_price(Decimal(user.wallet.current_balance))),
            "starting_reference": str(STARTING_PORTFOLIO_REFERENCE),
        },
        "holdings": holdings,
        "recent_trades": [
            {
                "id": trade.id,
                "symbol": trade.asset.symbol,
                "side": trade.side,
                "quantity": str(_quantize_quantity(Decimal(trade.quantity))),
                "price": str(_quantize_price(Decimal(trade.price))),
                "gross_amount": str(_quantize_price(Decimal(trade.gross_amount))),
                "created_at": trade.created_at.isoformat(),
            }
            for trade in recent_trades
        ],
    }


def get_public_portfolio_summary_by_handle(handle: str) -> dict:
    user = User.query.filter_by(handle=handle.strip().lower()).first()
    if user is None:
        raise PortfolioError("User not found.")

    private_portfolio = get_private_portfolio(user.id)
    summary = dict(private_portfolio["summary"])
    summary.pop("available_cash", None)
    summary.pop("starting_reference", None)
    summary["handle"] = user.handle
    return summary