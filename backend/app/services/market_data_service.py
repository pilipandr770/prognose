import threading
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from urllib.parse import quote

import requests
import yfinance as yf


SUPPORTED_ASSET_TYPES = {"stock", "crypto", "fund", "etf"}
SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
CHART_URL_TEMPLATE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
}
PRICE_PLACES = Decimal("0.01")
QUOTE_CACHE_TTL_SECONDS = 30
CRYPTO_SYMBOL_ALIASES = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "XRP": "XRP-USD",
    "DOGE": "DOGE-USD",
    "ADA": "ADA-USD",
    "BNB": "BNB-USD",
    "DOT": "DOT-USD",
    "AVAX": "AVAX-USD",
    "LTC": "LTC-USD",
    "LINK": "LINK-USD",
}


class MarketDataError(ValueError):
    pass


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(PRICE_PLACES, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        raise MarketDataError("Asset symbol is required.")
    normalized = CRYPTO_SYMBOL_ALIASES.get(normalized, normalized)
    return normalized


def _normalize_asset_type(raw_value: Any) -> str | None:
    value = str(raw_value or "").strip().upper()
    mapping = {
        "EQUITY": "stock",
        "STOCK": "stock",
        "CRYPTOCURRENCY": "crypto",
        "CRYPTO": "crypto",
        "ETF": "etf",
        "MUTUALFUND": "fund",
        "FUND": "fund",
    }
    normalized = mapping.get(value)
    if normalized in SUPPORTED_ASSET_TYPES:
        return normalized
    return None


def _request_json(url: str, *, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=15)
    try:
        payload = response.json()
    except ValueError as exc:
        raise MarketDataError("Yahoo Finance returned an unreadable response.") from exc

    if not response.ok:
        description = payload.get("finance", {}).get("error", {}).get("description")
        raise MarketDataError(description or f"Yahoo Finance request failed with HTTP {response.status_code}.")
    return payload


class YahooLiveQuoteStream:
    def __init__(self) -> None:
        self._enabled = True
        self._max_symbols = 24
        self._lock = threading.RLock()
        self._symbols: set[str] = set()
        self._quotes: dict[str, dict[str, Any]] = {}
        self._thread: threading.Thread | None = None
        self._active_socket: Any | None = None

    def configure(self, *, enabled: bool, max_symbols: int) -> None:
        with self._lock:
            self._enabled = enabled
            self._max_symbols = max(1, int(max_symbols or 1))

    def track_symbols(self, symbols: list[str]) -> None:
        normalized_symbols = []
        for symbol in symbols:
            try:
                normalized_symbols.append(_normalize_symbol(symbol))
            except MarketDataError:
                continue

        if not normalized_symbols:
            return

        with self._lock:
            if not self._enabled:
                return
            available_slots = max(self._max_symbols - len(self._symbols), 0)
            new_symbols = [symbol for symbol in normalized_symbols if symbol not in self._symbols][:available_slots]
            if not new_symbols:
                return
            self._symbols.update(new_symbols)
            active_socket = self._active_socket

        if active_socket is not None:
            try:
                active_socket.subscribe(new_symbols)
                return
            except Exception:
                pass

        self._ensure_thread_started()

    def get_quote(self, symbol: str) -> dict[str, Any] | None:
        normalized_symbol = _normalize_symbol(symbol)
        with self._lock:
            cached = self._quotes.get(normalized_symbol)
            return dict(cached) if cached else None

    def _ensure_thread_started(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._listen_forever, name="yahoo-live-quotes", daemon=True)
            self._thread.start()

    def _listen_forever(self) -> None:
        while True:
            with self._lock:
                enabled = self._enabled
                symbols = sorted(self._symbols)
            if not enabled:
                return
            if not symbols:
                time.sleep(1)
                continue

            socket = None
            try:
                socket = yf.WebSocket(verbose=False)
                with self._lock:
                    self._active_socket = socket
                socket.subscribe(symbols)
                socket.listen(self._handle_message)
            except Exception:
                time.sleep(3)
            finally:
                with self._lock:
                    if self._active_socket is socket:
                        self._active_socket = None
                if socket is not None:
                    try:
                        socket.close()
                    except Exception:
                        pass

    def _handle_message(self, message: dict[str, Any]) -> None:
        if not isinstance(message, dict):
            return

        symbol = message.get("id") or message.get("symbol")
        if not symbol:
            return

        normalized_symbol = str(symbol).strip().upper()
        current_price = _to_decimal(message.get("price"))
        if current_price is None:
            return

        previous_close = _to_decimal(message.get("previous_close"))
        change = _to_decimal(message.get("change"))
        change_percent = _to_decimal(message.get("change_percent"))

        with self._lock:
            existing = dict(self._quotes.get(normalized_symbol, {}))
            self._quotes[normalized_symbol] = {
                **existing,
                "symbol": normalized_symbol,
                "current_price": str(current_price),
                "previous_close": str(previous_close) if previous_close is not None else existing.get("previous_close"),
                "change": str(change) if change is not None else existing.get("change"),
                "change_percent": str(change_percent) if change_percent is not None else existing.get("change_percent"),
                "exchange": message.get("exchange") or existing.get("exchange"),
                "market_time": message.get("time") or existing.get("market_time"),
                "source": "yahoo_websocket",
            }


_live_quote_stream = YahooLiveQuoteStream()
_quote_details_cache: dict[str, dict[str, Any]] = {}
_quote_cache_lock = threading.RLock()
_search_limit = 8


def init_market_data(app) -> None:
    global _search_limit

    _search_limit = max(1, int(app.config.get("MARKET_DATA_SEARCH_LIMIT", 8)))
    _live_quote_stream.configure(
        enabled=bool(app.config.get("MARKET_DATA_WEBSOCKET_ENABLED", True)),
        max_symbols=int(app.config.get("MARKET_DATA_TRACKED_SYMBOL_LIMIT", 24)),
    )


def _normalize_search_item(raw_item: dict[str, Any]) -> dict[str, Any] | None:
    symbol = str(raw_item.get("symbol") or "").strip().upper()
    asset_type = _normalize_asset_type(raw_item.get("quoteType") or raw_item.get("typeDisp"))
    if not symbol or asset_type is None:
        return None

    return {
        "symbol": symbol,
        "name": raw_item.get("longname") or raw_item.get("shortname") or symbol,
        "asset_type": asset_type,
        "exchange": raw_item.get("exchDisp") or raw_item.get("exchange") or "n/a",
        "sector": raw_item.get("sectorDisp") or raw_item.get("sector") or "",
        "industry": raw_item.get("industryDisp") or raw_item.get("industry") or "",
    }


def search_market_assets(query: str, *, limit: int = 8) -> list[dict[str, Any]]:
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []

    payload = _request_json(
        SEARCH_URL,
        params={
            "q": normalized_query,
            "quotesCount": max(1, min(int(limit or 8), _search_limit)),
            "newsCount": 0,
            "enableFuzzyQuery": False,
        },
    )
    items = []
    seen_symbols: set[str] = set()
    for raw_item in payload.get("quotes", []):
        item = _normalize_search_item(raw_item)
        if item is None or item["symbol"] in seen_symbols:
            continue
        seen_symbols.add(item["symbol"])
        items.append(item)
    return items


def _compute_previous_close(meta: dict[str, Any], result: dict[str, Any]) -> Decimal | None:
    previous_close = _to_decimal(meta.get("previousClose") or meta.get("chartPreviousClose"))
    if previous_close is not None:
        return previous_close

    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    normalized_closes = [_to_decimal(value) for value in closes if value is not None]
    normalized_closes = [value for value in normalized_closes if value is not None]
    if len(normalized_closes) >= 2:
        return normalized_closes[-2]
    return None


def _fetch_chart_quote(symbol: str) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(symbol)
    payload = _request_json(
        CHART_URL_TEMPLATE.format(symbol=quote(normalized_symbol, safe="")),
        params={
            "interval": "1d",
            "range": "5d",
            "includePrePost": "false",
        },
    )

    results = payload.get("chart", {}).get("result") or []
    if not results:
        error = payload.get("chart", {}).get("error") or {}
        raise MarketDataError(error.get("description") or f"Yahoo Finance does not have market data for {normalized_symbol}.")

    result = results[0]
    meta = result.get("meta") or {}
    asset_type = _normalize_asset_type(meta.get("instrumentType"))
    if asset_type is None:
        raise MarketDataError(f"{normalized_symbol} is not a supported stock, crypto or fund asset.")

    current_price = _to_decimal(meta.get("regularMarketPrice") or meta.get("previousClose") or meta.get("chartPreviousClose"))
    if current_price is None:
        raise MarketDataError(f"Yahoo Finance did not return a price for {normalized_symbol}.")

    previous_close = _compute_previous_close(meta, result)
    change = None
    change_percent = None
    if current_price is not None and previous_close not in (None, Decimal("0.00")):
        change = (current_price - previous_close).quantize(PRICE_PLACES, rounding=ROUND_HALF_UP)
        change_percent = (change / previous_close * Decimal("100")).quantize(PRICE_PLACES, rounding=ROUND_HALF_UP)

    day_high = _to_decimal(meta.get("regularMarketDayHigh"))
    day_low = _to_decimal(meta.get("regularMarketDayLow"))

    return {
        "symbol": normalized_symbol,
        "name": meta.get("longName") or meta.get("shortName") or normalized_symbol,
        "asset_type": asset_type,
        "currency": meta.get("currency") or "USD",
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName") or meta.get("exchange") or "n/a",
        "current_price": str(current_price),
        "previous_close": str(previous_close) if previous_close is not None else None,
        "day_high": str(day_high) if day_high is not None else None,
        "day_low": str(day_low) if day_low is not None else None,
        "volume": str(meta.get("regularMarketVolume")) if meta.get("regularMarketVolume") is not None else None,
        "change": str(change) if change is not None else None,
        "change_percent": str(change_percent) if change_percent is not None else None,
        "market_time": str(meta.get("regularMarketTime")) if meta.get("regularMarketTime") is not None else None,
        "source": "yahoo_chart",
    }


def _merge_live_quote(base_quote: dict[str, Any], live_quote: dict[str, Any] | None) -> dict[str, Any]:
    if not live_quote:
        return base_quote

    merged = dict(base_quote)
    if live_quote.get("current_price") is not None:
        merged["current_price"] = live_quote["current_price"]
    if live_quote.get("exchange"):
        merged["exchange"] = live_quote["exchange"]
    if live_quote.get("market_time"):
        merged["market_time"] = live_quote["market_time"]

    previous_close = _to_decimal(merged.get("previous_close"))
    current_price = _to_decimal(merged.get("current_price"))
    if current_price is not None and previous_close not in (None, Decimal("0.00")):
        change = (current_price - previous_close).quantize(PRICE_PLACES, rounding=ROUND_HALF_UP)
        change_percent = (change / previous_close * Decimal("100")).quantize(PRICE_PLACES, rounding=ROUND_HALF_UP)
        merged["change"] = str(change)
        merged["change_percent"] = str(change_percent)
    merged["source"] = live_quote.get("source") or merged.get("source")
    return merged


def get_market_quote(symbol: str, *, track: bool = True, force_refresh: bool = False) -> dict[str, Any]:
    normalized_symbol = _normalize_symbol(symbol)
    if track:
        _live_quote_stream.track_symbols([normalized_symbol])

    with _quote_cache_lock:
        cached = _quote_details_cache.get(normalized_symbol)

    now = time.time()
    if cached and not force_refresh and now - cached["fetched_at"] < QUOTE_CACHE_TTL_SECONDS:
        base_quote = dict(cached["payload"])
    else:
        base_quote = _fetch_chart_quote(normalized_symbol)
        with _quote_cache_lock:
            _quote_details_cache[normalized_symbol] = {"payload": dict(base_quote), "fetched_at": now}

    return _merge_live_quote(base_quote, _live_quote_stream.get_quote(normalized_symbol))


def get_market_quotes(symbols: list[str]) -> list[dict[str, Any]]:
    items = []
    for symbol in symbols:
        try:
            items.append(get_market_quote(symbol, track=True))
        except MarketDataError:
            continue
    return items