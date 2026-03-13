from __future__ import annotations

from datetime import datetime, timezone
from time import time
from typing import Dict

import httpx

from app.core.config import settings


class AlphaVantageService:
    def __init__(self) -> None:
        self._client = httpx.Client(timeout=10.0)
        self._api_key = settings.ALPHAVANTAGE_API_KEY
        self._base_url = settings.ALPHAVANTAGE_BASE_URL
        self._cache: Dict[str, tuple[float, dict]] = {}
        self._rate_limited_until: float = 0.0

    def _cache_get(self, symbol: str, ttl: int) -> dict | None:
        cached = self._cache.get(symbol)
        if not cached:
            return None
        ts, data = cached
        if time() - ts > ttl:
            return None
        return data

    def _cache_get_any(self, symbol: str) -> dict | None:
        cached = self._cache.get(symbol)
        if not cached:
            return None
        return cached[1]

    def _cache_set(self, symbol: str, data: dict) -> None:
        self._cache[symbol] = (time(), data)

    def get_global_quote(self, symbol: str) -> dict:
        if not self._api_key:
            raise ValueError("ALPHAVANTAGE_API_KEY is not set")

        cached = self._cache_get(symbol, ttl=300)
        if cached:
            return cached
        if time() < self._rate_limited_until:
            cached_any = self._cache_get_any(symbol)
            if cached_any:
                return cached_any
            raise ValueError("Alpha Vantage rate limit reached. Please wait about a minute and try again.")

        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self._api_key,
        }
        res = self._client.get(self._base_url, params=params)
        res.raise_for_status()
        data = res.json()

        if "Note" in data or "Error Message" in data or "Information" in data:
            message = (
                data.get("Note")
                or data.get("Error Message")
                or data.get("Information")
                or "Alpha Vantage error"
            )
            if "Thank you for using Alpha Vantage" in message or "standard API call frequency" in message:
                self._rate_limited_until = time() + 65
            raise ValueError(message)

        quote = data.get("Global Quote", {})
        if not quote:
            raise ValueError("Alpha Vantage returned no quote")

        def as_float(value: str | None) -> float:
            try:
                return float(value) if value is not None else 0.0
            except ValueError:
                return 0.0

        normalized = {
            "c": as_float(quote.get("05. price")),
            "h": as_float(quote.get("03. high")),
            "l": as_float(quote.get("04. low")),
            "o": as_float(quote.get("02. open")),
            "pc": as_float(quote.get("08. previous close")),
        }

        self._cache_set(symbol, normalized)
        return normalized

    def get_first_quote(self, symbols: list[str]) -> dict:
        last_error: Exception | None = None
        for candidate in symbols:
            try:
                return self.get_global_quote(candidate)
            except Exception as exc:  # pragma: no cover - fallback tries multiple symbols
                last_error = exc
                message = str(exc)
                if "rate limit" in message.lower() or "Thank you for using Alpha Vantage" in message:
                    break
                continue
        if last_error:
            raise last_error
        raise ValueError("Alpha Vantage returned no quote")

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> dict:
        if not self._api_key:
            raise ValueError("ALPHAVANTAGE_API_KEY is not set")

        from_code = from_currency.upper()
        to_code = to_currency.upper()
        cache_key = f"FX:{from_code}:{to_code}"

        cached = self._cache_get(cache_key, ttl=300)
        if cached:
            return cached
        if time() < self._rate_limited_until:
            cached_any = self._cache_get_any(cache_key)
            if cached_any:
                return cached_any
            raise ValueError("Alpha Vantage rate limit reached. Please wait about a minute and try again.")

        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_code,
            "to_currency": to_code,
            "apikey": self._api_key,
        }
        res = self._client.get(self._base_url, params=params)
        res.raise_for_status()
        data = res.json()

        if "Note" in data or "Error Message" in data or "Information" in data:
            message = (
                data.get("Note")
                or data.get("Error Message")
                or data.get("Information")
                or "Alpha Vantage error"
            )
            if "Thank you for using Alpha Vantage" in message or "standard API call frequency" in message:
                self._rate_limited_until = time() + 65
            raise ValueError(message)

        raw = data.get("Realtime Currency Exchange Rate", {})
        if not raw:
            raise ValueError("Alpha Vantage returned no exchange rate")

        def as_float(value: str | None) -> float:
            try:
                return float(value) if value is not None else 0.0
            except ValueError:
                return 0.0

        normalized = {
            "from": raw.get("1. From_Currency Code", from_code),
            "to": raw.get("3. To_Currency Code", to_code),
            "rate": as_float(raw.get("5. Exchange Rate")),
            "bid": as_float(raw.get("8. Bid Price")),
            "ask": as_float(raw.get("9. Ask Price")),
            "last_refreshed": raw.get("6. Last Refreshed"),
            "timezone": raw.get("7. Time Zone"),
        }

        self._cache_set(cache_key, normalized)
        return normalized

    def get_daily_series(self, symbol: str, output_size: str = "compact") -> list[dict]:
        if not self._api_key:
            raise ValueError("ALPHAVANTAGE_API_KEY is not set")

        cache_key = f"DAILY:{symbol}:{output_size}"
        cached = self._cache_get(cache_key, ttl=21600)
        if cached:
            return cached.get("series", [])
        if time() < self._rate_limited_until:
            cached_any = self._cache_get_any(cache_key)
            if cached_any:
                return cached_any.get("series", [])
            raise ValueError("Alpha Vantage rate limit reached. Please wait about a minute and try again.")

        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": output_size,
            "apikey": self._api_key,
        }
        res = self._client.get(self._base_url, params=params)
        res.raise_for_status()
        data = res.json()

        if "Note" in data or "Error Message" in data or "Information" in data:
            message = (
                data.get("Note")
                or data.get("Error Message")
                or data.get("Information")
                or "Alpha Vantage error"
            )
            if "Thank you for using Alpha Vantage" in message or "standard API call frequency" in message:
                self._rate_limited_until = time() + 65
            raise ValueError(message)

        raw_series = data.get("Time Series (Daily)")
        if not raw_series or not isinstance(raw_series, dict):
            raise ValueError("Alpha Vantage returned no daily series")

        def as_float(value: str | None) -> float:
            try:
                return float(value) if value is not None else 0.0
            except ValueError:
                return 0.0

        series: list[dict] = []
        for day, values in raw_series.items():
            if not isinstance(values, dict):
                continue
            close = values.get("4. close") or values.get("5. adjusted close")
            ts = int(
                datetime.strptime(day, "%Y-%m-%d")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            series.append({"t": ts, "c": as_float(close)})

        series.sort(key=lambda item: item["t"])
        self._cache_set(cache_key, {"series": series})
        return series
