from decimal import Decimal

from app.extensions import db
from app.models.base import BaseModel


class PortfolioPosition(BaseModel):
    __tablename__ = "portfolio_positions"
    __table_args__ = (db.UniqueConstraint("user_id", "asset_id", name="uq_portfolio_user_asset"),)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    quantity = db.Column(db.Numeric(18, 8), nullable=False, default=Decimal("0"), server_default="0")
    average_cost = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    realized_pnl = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default="0")

    asset = db.relationship("Asset")
    trades = db.relationship(
        "PortfolioTrade",
        back_populates="position",
        cascade="all, delete-orphan",
        order_by="PortfolioTrade.id.desc()",
    )


class PortfolioWatchlistItem(BaseModel):
    __tablename__ = "portfolio_watchlist_items"
    __table_args__ = (db.UniqueConstraint("user_id", "asset_id", name="uq_watchlist_user_asset"),)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)

    asset = db.relationship("Asset")


class PortfolioTrade(BaseModel):
    __tablename__ = "portfolio_trades"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    position_id = db.Column(db.Integer, db.ForeignKey("portfolio_positions.id"), nullable=False, index=True)
    side = db.Column(db.String(8), nullable=False)
    quantity = db.Column(db.Numeric(18, 8), nullable=False)
    price = db.Column(db.Numeric(18, 2), nullable=False)
    gross_amount = db.Column(db.Numeric(18, 2), nullable=False)

    position = db.relationship("PortfolioPosition", back_populates="trades")
    asset = db.relationship("Asset")
