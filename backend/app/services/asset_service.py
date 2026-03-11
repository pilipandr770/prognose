from decimal import Decimal, ROUND_HALF_UP

from app.extensions import db
from app.models.asset import Asset, AssetPriceSnapshot


PRICE_PLACES = Decimal("0.01")


class AssetError(ValueError):
    pass


def _normalize_price(value: Decimal) -> Decimal:
    return Decimal(value).quantize(PRICE_PLACES, rounding=ROUND_HALF_UP)


def create_asset(*, symbol: str, name: str, asset_type: str, current_price: Decimal) -> Asset:
    normalized_symbol = symbol.strip().upper()
    if Asset.query.filter_by(symbol=normalized_symbol).first():
        raise AssetError("Asset symbol already exists.")

    asset = Asset(
        symbol=normalized_symbol,
        name=name.strip(),
        asset_type=asset_type.strip().lower(),
        current_price=_normalize_price(current_price),
    )
    db.session.add(asset)
    db.session.flush()
    db.session.add(AssetPriceSnapshot(asset_id=asset.id, price=asset.current_price, source="manual"))
    db.session.commit()
    return asset


def update_asset_price(*, asset_id: int, new_price: Decimal, source: str = "manual") -> Asset:
    asset = Asset.query.filter_by(id=asset_id).first()
    if asset is None:
        raise AssetError("Asset not found.")

    asset.current_price = _normalize_price(new_price)
    db.session.add(AssetPriceSnapshot(asset_id=asset.id, price=asset.current_price, source=source))
    db.session.commit()
    return asset


def get_asset_by_symbol(symbol: str) -> Asset | None:
    return Asset.query.filter_by(symbol=symbol.strip().upper()).first()


def sync_market_asset(
    *,
    symbol: str,
    name: str,
    asset_type: str,
    current_price: Decimal,
    source: str = "yahoo_sync",
    commit: bool = True,
) -> Asset:
    normalized_symbol = symbol.strip().upper()
    normalized_name = name.strip() or normalized_symbol
    normalized_type = asset_type.strip().lower()
    normalized_price = _normalize_price(current_price)

    asset = Asset.query.filter_by(symbol=normalized_symbol).first()
    if asset is None:
        asset = Asset(
            symbol=normalized_symbol,
            name=normalized_name,
            asset_type=normalized_type,
            current_price=normalized_price,
            is_active=True,
        )
        db.session.add(asset)
        db.session.flush()
        db.session.add(AssetPriceSnapshot(asset_id=asset.id, price=asset.current_price, source=source))
    else:
        asset.name = normalized_name
        asset.asset_type = normalized_type
        asset.is_active = True
        if Decimal(asset.current_price) != normalized_price:
            asset.current_price = normalized_price
            db.session.add(AssetPriceSnapshot(asset_id=asset.id, price=asset.current_price, source=source))

    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return asset


def list_assets() -> list[Asset]:
    return Asset.query.filter_by(is_active=True).order_by(Asset.symbol.asc()).all()
