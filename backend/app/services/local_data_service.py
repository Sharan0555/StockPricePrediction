from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from random import Random
from typing import Dict, List


class LocalDataService:
    def __init__(self) -> None:
        self._series_cache: Dict[str, List[dict]] = {}

    def _seed(self, symbol: str) -> int:
        digest = sha256(symbol.encode("utf-8")).hexdigest()
        return int(digest[:12], 16)

    def _profile(self, rng: Random, currency: str) -> dict:
        roll = rng.random()
        if roll < 0.25:
            profile = {
                "name": "defensive",
                "vol": 0.0075,
                "drift": 0.00025,
                "jump_prob": 0.008,
                "mean_revert": 0.08,
            }
        elif roll < 0.7:
            profile = {
                "name": "core",
                "vol": 0.011,
                "drift": 0.00035,
                "jump_prob": 0.012,
                "mean_revert": 0.06,
            }
        else:
            profile = {
                "name": "high_beta",
                "vol": 0.018,
                "drift": 0.00055,
                "jump_prob": 0.02,
                "mean_revert": 0.04,
            }
        if currency == "INR":
            profile["vol"] *= 1.1
            profile["drift"] *= 1.05
        return profile

    def _base_price(self, rng: Random, currency: str, profile: dict) -> float:
        if currency == "INR":
            low, high = 60, 4800
        else:
            low, high = 8, 700
        if profile["name"] == "defensive":
            low *= 1.1
            high *= 1.4
        elif profile["name"] == "high_beta":
            low *= 0.6
            high *= 0.9
        return rng.uniform(low, high)

    def _generate_series(self, symbol: str, currency: str, days: int) -> List[dict]:
        rng = Random(self._seed(symbol))
        profile = self._profile(rng, currency)
        base = self._base_price(rng, currency, profile)

        price = base
        series: List[dict] = []
        end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=days)

        remaining = days
        regimes: List[tuple[int, float, float]] = []
        while remaining > 0:
            length = min(remaining, rng.randint(25, 90))
            drift = profile["drift"] + rng.uniform(-0.0009, 0.0009)
            vol = profile["vol"] * rng.uniform(0.7, 1.35)
            regimes.append((length, drift, vol))
            remaining -= length

        regime_idx = 0
        regime_day = 0
        rolling: List[float] = []
        rolling_sum = 0.0

        for i in range(days):
            if regime_day >= regimes[regime_idx][0] and regime_idx < len(regimes) - 1:
                regime_idx += 1
                regime_day = 0
            _, drift, vol = regimes[regime_idx]

            day = start_date + timedelta(days=i + 1)
            day_of_week = day.weekday()
            seasonality = {
                0: -0.0001,
                1: 0.00015,
                2: 0.0002,
                3: 0.00015,
                4: -0.0002,
            }.get(day_of_week, 0.0)

            shock = rng.gauss(0.0, vol)
            if rng.random() < profile["jump_prob"]:
                shock += rng.gauss(0.0, vol * 4.0)

            mean_revert = 0.0
            if len(rolling) >= 50:
                sma50 = rolling_sum / len(rolling)
                if sma50 > 0:
                    mean_revert = profile["mean_revert"] * ((sma50 - price) / sma50)

            ret = drift + seasonality + shock + mean_revert
            price = max(base * 0.15, price * (1 + ret))

            rolling.append(price)
            rolling_sum += price
            if len(rolling) > 50:
                rolling_sum -= rolling.pop(0)

            ts = int(day.timestamp())
            series.append({"t": ts, "c": round(price, 2)})
            regime_day += 1

        return series

    def get_series(self, symbol: str, currency: str, days: int) -> List[dict]:
        cache_key = f"{symbol}:{currency}"
        series = self._series_cache.get(cache_key)
        if not series:
            series = self._generate_series(symbol, currency, max(days, 180))
            self._series_cache[cache_key] = series
        if days and len(series) > days:
            return series[-days:]
        return series

    def get_quote(self, symbol: str, currency: str) -> dict:
        series = self.get_series(symbol, currency, days=2)
        if not series:
            return {"c": 0.0, "h": 0.0, "l": 0.0, "o": 0.0, "pc": 0.0}
        last = float(series[-1]["c"])
        prev = float(series[-2]["c"]) if len(series) > 1 else last
        rng = Random(self._seed(symbol) + int(series[-1]["t"]))
        intraday_range = max(abs(last - prev), last * rng.uniform(0.002, 0.01))
        high = max(last, prev) + intraday_range
        low = max(min(last, prev) - intraday_range, last * 0.85, 0.01)
        open_price = prev * (1 + rng.uniform(-0.003, 0.003))
        return {
            "c": round(last, 2),
            "h": round(high, 2),
            "l": round(low, 2),
            "o": round(open_price, 2),
            "pc": round(prev, 2),
        }
