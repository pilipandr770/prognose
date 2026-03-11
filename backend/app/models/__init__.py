from app.models.asset import Asset, AssetPriceSnapshot
from app.models.base import BaseModel
from app.models.billing import Subscription, SubscriptionPlan
from app.models.email_verification import EmailVerificationToken
from app.models.event import Event, EventOutcome
from app.models.leaderboard import LeaderboardSnapshot
from app.models.portfolio import PortfolioPosition, PortfolioTrade, PortfolioWatchlistItem
from app.models.prediction import PredictionPosition
from app.models.social import FollowRelation
from app.models.user import User
from app.models.wallet import Wallet, WalletEntry


def register_models() -> None:
	# Import models so SQLAlchemy metadata is populated before migrations/tests.
	return None


__all__ = [
	"BaseModel",
	"Asset",
	"AssetPriceSnapshot",
	"EmailVerificationToken",
	"Event",
	"EventOutcome",
	"FollowRelation",
	"LeaderboardSnapshot",
	"PortfolioPosition",
	"PortfolioTrade",
	"PortfolioWatchlistItem",
	"PredictionPosition",
	"Subscription",
	"SubscriptionPlan",
	"User",
	"Wallet",
	"WalletEntry",
	"register_models",
]
