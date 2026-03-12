from urllib.parse import urlparse

from app.models.user import User


class ProfileError(ValueError):
    pass


DISPLAY_NAME_LIMIT = 80
BIO_LIMIT = 500
LOCATION_LIMIT = 80
WEBSITE_URL_LIMIT = 255


def _normalize_optional_text(value, *, limit: int, field_name: str) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    if not normalized:
        return None
    if len(normalized) > limit:
        raise ProfileError(f"{field_name} must be {limit} characters or fewer.")
    return normalized


def _normalize_website_url(value) -> str | None:
    normalized = _normalize_optional_text(value, limit=WEBSITE_URL_LIMIT, field_name="website_url")
    if normalized is None:
        return None

    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProfileError("website_url must be a valid http or https URL.")
    return normalized


def serialize_profile_fields(user: User) -> dict:
    return {
        "display_name": user.display_name,
        "bio": user.bio,
        "location": user.location,
        "website_url": user.website_url,
        "joined_at": user.created_at.isoformat() if user.created_at else None,
    }


def update_user_profile(
    user: User,
    *,
    display_name=None,
    bio=None,
    location=None,
    website_url=None,
) -> User:
    user.display_name = _normalize_optional_text(display_name, limit=DISPLAY_NAME_LIMIT, field_name="display_name")
    user.bio = _normalize_optional_text(bio, limit=BIO_LIMIT, field_name="bio")
    user.location = _normalize_optional_text(location, limit=LOCATION_LIMIT, field_name="location")
    user.website_url = _normalize_website_url(website_url)
    return user
