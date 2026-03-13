from typing import Any, Dict, List, Union

import httpx

from app.core.config import settings


class FinnhubService:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.FINNHUB_BASE_URL,
            timeout=10.0,
            follow_redirects=True,
        )
        self._api_key = settings.FINNHUB_API_KEY

    def _get(
        self, path: str, params: Dict[str, Any] | None = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        params = params or {}
        params["token"] = self._api_key
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def search_symbol(self, query: str) -> List[Dict[str, Any]]:
        data = self._get("/search", {"q": query})
        return data.get("result", [])

    def get_realtime_quote(self, symbol: str) -> Dict[str, Any]:
        return self._get("/quote", {"symbol": symbol})

    def get_candles(
        self,
        symbol: str,
        resolution: str,
        from_unix: int,
        to_unix: int,
    ) -> Dict[str, Any]:
        return self._get(
            "/stock/candle",
            {
                "symbol": symbol,
                "resolution": resolution,
                "from": from_unix,
                "to": to_unix,
            },
        )

    def list_symbols(self, exchange: str = "US") -> List[Dict[str, Any]]:
        data = self._get("/stock/symbol", {"exchange": exchange})
        # Finnhub returns a JSON array for this endpoint
        return data if isinstance(data, list) else []
