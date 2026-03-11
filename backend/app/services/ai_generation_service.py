import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html import unescape
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from flask import current_app
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.event import Event
from app.models.user import User
from app.services.billing_service import assign_default_subscription
from app.services.event_service import EventError, create_event
from app.services.prediction_service import PredictionError, place_prediction
from app.services.wallet_service import create_wallet_entry, create_wallet_for_user, grant_signup_balance


class AIEventGenerationError(ValueError):
    pass


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _strip_html(raw_html: str) -> str:
    without_scripts = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return _collapse_whitespace(unescape(without_tags))


def _fetch_source_brief(url: str) -> dict:
    timeout = current_app.config["AI_SOURCE_TIMEOUT_SECONDS"]
    char_limit = current_app.config["AI_SOURCE_TEXT_CHAR_LIMIT"]
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            raw_body = response.read(char_limit * 4).decode("utf-8", errors="ignore")
            content_type = response.headers.get("Content-Type", "")
    except URLError as exc:
        raise AIEventGenerationError(f"Failed to fetch source URL {url}: {exc}") from exc

    body = _strip_html(raw_body) if "html" in content_type.lower() or "<html" in raw_body.lower() else _collapse_whitespace(raw_body)
    if not body:
        raise AIEventGenerationError(f"Source URL {url} returned empty content.")

    return {"url": url, "snippet": body[:char_limit]}


def _normalize_source_note(note: str, index: int) -> dict | None:
    normalized = _collapse_whitespace(note)
    if not normalized:
        return None
    return {"url": f"operator-note-{index}", "snippet": normalized[: current_app.config["AI_SOURCE_TEXT_CHAR_LIMIT"]]}


def _collect_source_briefs(*, source_urls: list[str], source_notes: list[str]) -> tuple[list[dict], list[str]]:
    source_briefs = []
    warnings = []

    for index, note in enumerate(source_notes, start=1):
        normalized_note = _normalize_source_note(note, index)
        if normalized_note is not None:
            source_briefs.append(normalized_note)

    for url in source_urls:
        try:
            source_briefs.append(_fetch_source_brief(url))
        except AIEventGenerationError as exc:
            warnings.append(str(exc))

    return source_briefs, warnings


def _extract_json_object(raw_text: str) -> dict:
    normalized = raw_text.strip()
    if normalized.startswith("```"):
        normalized = re.sub(r"^```(?:json)?|```$", "", normalized, flags=re.IGNORECASE | re.MULTILINE).strip()

    if not normalized:
        raise AIEventGenerationError("OpenAI response was empty.")

    if not normalized.startswith("{"):
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start != -1 and end != -1 and end > start:
            normalized = normalized[start : end + 1]

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise AIEventGenerationError("OpenAI response is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise AIEventGenerationError("OpenAI response JSON must be an object.")
    return payload


def _normalize_decimal(value: object, default: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _validate_candidate(candidate: dict, *, now: datetime, existing_titles: set[str]) -> dict | None:
    title = _collapse_whitespace(str(candidate.get("title") or ""))
    description = _collapse_whitespace(str(candidate.get("description") or ""))
    category = _collapse_whitespace(str(candidate.get("category") or "markets")).lower()
    source_of_truth = _collapse_whitespace(str(candidate.get("source_of_truth") or ""))
    rationale = _collapse_whitespace(str(candidate.get("rationale") or ""))
    selection_reason = _collapse_whitespace(str(candidate.get("selection_reason") or rationale))
    normalized_outcomes = []
    for item in (candidate.get("outcomes") or []):
        if isinstance(item, dict):
            label = item.get("label") or item.get("name") or item.get("outcome") or ""
        else:
            label = item
        normalized_label = _collapse_whitespace(str(label))
        if normalized_label:
            normalized_outcomes.append(normalized_label)
    outcomes = normalized_outcomes

    if not title or not source_of_truth or len(outcomes) != 2:
        return None
    if title.lower() in existing_titles:
        return None

    try:
        hours_to_close = int(candidate.get("hours_to_close", 48))
        hours_to_resolve = int(candidate.get("hours_to_resolve", hours_to_close + 24))
    except (TypeError, ValueError):
        return None

    min_close_hours = current_app.config["AI_MIN_CLOSE_HOURS"]
    if hours_to_close < min_close_hours or hours_to_resolve <= hours_to_close:
        return None

    confidence = max(0.0, min(float(candidate.get("confidence", 0.5)), 0.99))
    recommended_outcome = _collapse_whitespace(str(candidate.get("recommended_outcome") or outcomes[0]))
    if recommended_outcome.lower() not in {outcome.lower() for outcome in outcomes}:
        recommended_outcome = outcomes[0]

    recommended_stake = _normalize_decimal(candidate.get("recommended_stake") or "50.00", "50.00")
    if recommended_stake <= Decimal("0.00"):
        recommended_stake = Decimal("50.00")
    if recommended_stake > Decimal("250.00"):
        recommended_stake = Decimal("250.00")

    return {
        "title": title,
        "description": description,
        "category": category,
        "source_of_truth": source_of_truth,
        "outcomes": outcomes,
        "closes_at": (now + timedelta(hours=hours_to_close)).isoformat(),
        "resolves_at": (now + timedelta(hours=hours_to_resolve)).isoformat(),
        "confidence": round(confidence, 2),
        "rationale": rationale,
        "selection_reason": selection_reason,
        "recommended_outcome": recommended_outcome,
        "recommended_stake": str(recommended_stake.quantize(Decimal("0.01"))),
    }


def ensure_ai_operator_user() -> User:
    email = current_app.config["AI_BOT_EMAIL"].strip().lower()
    handle = current_app.config["AI_BOT_HANDLE"].strip().lower()
    user = User.query.filter_by(email=email).first()
    if user is not None:
        return user

    user = User(
        email=email,
        handle=handle,
        password_hash=generate_password_hash(uuid4().hex),
        email_verified=True,
        verification_status="system_generated",
        is_active=True,
        is_admin=False,
    )
    db.session.add(user)
    db.session.flush()
    wallet = create_wallet_for_user(user.id)
    grant_signup_balance(wallet.id)
    assign_default_subscription(user.id)
    db.session.commit()
    return user


def _credit_ai_bot_if_needed(bot_user: User, minimum_balance: Decimal) -> None:
    current_balance = Decimal(bot_user.wallet.current_balance or 0)
    if current_balance >= minimum_balance:
        return

    deficit = minimum_balance - current_balance
    create_wallet_entry(
        wallet_id=bot_user.wallet.id,
        entry_type="credit",
        amount=deficit,
        reason_code="ai_bot_topup",
        idempotency_key=f"ai-bot-topup:{bot_user.id}:{uuid4().hex}",
        reference_type="system",
        reference_id=str(bot_user.id),
    )
    db.session.commit()


def _call_openai_for_candidates(*, topics: str, count: int, source_briefs: list[dict]) -> list[dict]:
    api_key = current_app.config["OPENAI_API_KEY"]
    if not api_key:
        raise AIEventGenerationError("OPENAI_API_KEY is not configured.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AIEventGenerationError("openai package is not installed.") from exc

    model = current_app.config["OPENAI_MODEL"]
    source_block = "\n\n".join([f"URL: {item['url']}\nSnippet: {item['snippet']}" for item in source_briefs])
    system_prompt = (
        "You generate game prediction events for a virtual-money platform. "
        "Only produce binary events with clear resolution criteria, near-term time windows, and broad interest. "
        "Avoid death, injury, extremist, sexual, illegal, or vague topics. "
        "Prefer macro, politics, company catalysts, sports schedules, and other officially resolvable events. "
        "Return strict JSON with an 'events' array."
    )
    user_prompt = (
        f"Generate up to {count} event candidates.\n"
        f"Operator topics: {topics or 'general market-moving scheduled events'}\n"
        "For each event return: title, description, category, source_of_truth, outcomes, hours_to_close, hours_to_resolve, "
        "confidence, rationale, selection_reason, recommended_outcome, recommended_stake.\n"
        "Use only outcomes ['Yes','No'] unless the source strongly requires a different binary wording.\n"
        "Use source_of_truth as the final official resolution source, not a commentary source.\n"
        f"Source material:\n{source_block}"
    )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    message = response.choices[0].message.content if response.choices else ""
    payload = _extract_json_object(message or "")
    events = payload.get("events") or []
    if not isinstance(events, list):
        raise AIEventGenerationError("OpenAI response does not contain a valid events array.")
    return events


def generate_ai_event_batch(
    *,
    admin_user_id: int,
    topics: str,
    count: int,
    source_urls: list[str] | None = None,
    source_notes: list[str] | None = None,
    publish_generated: bool = False,
    create_seed_predictions: bool = False,
) -> dict:
    max_count = current_app.config["AI_EVENT_GENERATION_MAX_COUNT"]
    normalized_count = min(max(1, count), max_count)

    if source_urls is None:
        resolved_source_urls = [value.strip() for value in current_app.config["AI_DEFAULT_SOURCE_URLS"] if value.strip()]
    else:
        resolved_source_urls = [value.strip() for value in source_urls if value.strip()]
    resolved_source_urls = resolved_source_urls[: current_app.config["AI_MAX_SOURCE_URLS"]]
    resolved_source_notes = [value for value in (source_notes or []) if _collapse_whitespace(value)]
    total_notes_chars = sum(len(value) for value in resolved_source_notes)
    if total_notes_chars > 6000:
        raise AIEventGenerationError(
            "Source notes are too large. Keep only a few short paragraphs or bullet points, up to 6000 characters total."
        )

    source_briefs, warnings = _collect_source_briefs(source_urls=resolved_source_urls, source_notes=resolved_source_notes)

    if not source_briefs:
        warning_suffix = f" Warnings: {' | '.join(warnings)}" if warnings else ""
        raise AIEventGenerationError(
            "Provide at least one usable source URL or pasted source note for AI generation." + warning_suffix
        )

    existing_titles = {event.title.strip().lower() for event in Event.query.all() if event.title}
    raw_candidates = _call_openai_for_candidates(topics=topics, count=normalized_count, source_briefs=source_briefs)
    now = datetime.now(timezone.utc)

    published_items = []
    results = []
    for candidate in raw_candidates:
        if len(results) >= normalized_count:
            break
        if not isinstance(candidate, dict):
            continue
        normalized = _validate_candidate(candidate, now=now, existing_titles=existing_titles)
        if normalized is None:
            continue
        existing_titles.add(normalized["title"].lower())

        result_item = {**normalized, "publication_status": "suggested", "event_id": None, "seed_prediction": None}
        if publish_generated:
            try:
                event = create_event(
                    creator_id=admin_user_id,
                    title=normalized["title"],
                    description=normalized["description"],
                    category=normalized["category"],
                    source_of_truth=normalized["source_of_truth"],
                    closes_at=datetime.fromisoformat(normalized["closes_at"]),
                    resolves_at=datetime.fromisoformat(normalized["resolves_at"]),
                    outcomes=normalized["outcomes"],
                    force_pending_review=True,
                )
            except EventError as exc:
                result_item["publication_status"] = "rejected"
                result_item["publication_error"] = str(exc)
                results.append(result_item)
                continue

            result_item["publication_status"] = "queued_for_review"
            result_item["event_id"] = event.id
            result_item["event_status"] = event.status
            published_items.append((event, result_item))

        results.append(result_item)

    if publish_generated and create_seed_predictions and published_items:
        open_items = [(event, result_item) for event, result_item in published_items if event.status == "open"]
        pending_items = [(event, result_item) for event, result_item in published_items if event.status != "open"]

        for _event, result_item in pending_items:
            result_item["seed_prediction"] = {
                "status": "skipped",
                "reason": "Seed prediction skipped until the event passes admin moderation.",
            }

        if open_items:
            bot_user = ensure_ai_operator_user()
            total_required = sum([Decimal(item[1]["recommended_stake"]) for item in open_items], Decimal("0.00"))
            _credit_ai_bot_if_needed(bot_user, total_required)

        for event, result_item in open_items:
            recommended_outcome = result_item["recommended_outcome"].lower()
            outcome = next((value for value in event.outcomes if value.label.lower() == recommended_outcome), None)
            if outcome is None:
                result_item["seed_prediction"] = {"status": "skipped", "reason": "Recommended outcome not found on created event."}
                continue

            try:
                position = place_prediction(
                    user_id=bot_user.id,
                    event_id=event.id,
                    outcome_id=outcome.id,
                    stake_amount=Decimal(result_item["recommended_stake"]),
                )
                result_item["seed_prediction"] = {
                    "status": "created",
                    "user_handle": bot_user.handle,
                    "prediction_id": position.id,
                    "outcome_label": outcome.label,
                    "stake_amount": result_item["recommended_stake"],
                    "share_quantity": str(position.share_quantity),
                }
            except PredictionError as exc:
                result_item["seed_prediction"] = {"status": "failed", "reason": str(exc)}

    return {
        "used_model": current_app.config["OPENAI_MODEL"],
        "publish_generated": publish_generated,
        "create_seed_predictions": create_seed_predictions,
        "source_briefs": source_briefs,
        "warnings": warnings,
        "items": results,
    }