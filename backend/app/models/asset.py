from decimal import Decimal

from app.extensions import db
from app.models.base import BaseModel


class Asset(BaseModel):
    __tablename__ = "assets"

    symbol = db.Column(db.String(32), nullable=False, unique=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    asset_type = db.Column(db.String(32), nullable=False, index=True)
    current_price = db.Column(db.Numeric(18, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.text("true"))

    snapshots = db.relationship(
        "AssetPriceSnapshot",
        back_populates="asset",
        cascade="all, delete-orphan",
        order_by="AssetPriceSnapshot.id.desc()",
    )


class AssetPriceSnapshot(BaseModel):
    __tablename__ = "asset_price_snapshots"

    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True)
    price = db.Column(db.Numeric(18, 2), nullable=False)
    source = db.Column(db.String(64), nullable=False, default="manual", server_default="manual")

    asset = db.relationship("Asset", back_populates="snapshots")
