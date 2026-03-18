from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from typing import Iterable, List

import numpy as np

from app.core.config import settings
from app.services.alpha_vantage_service import AlphaVantageService
from app.services.finnhub_service import FinnhubService
from app.services.local_data_service import LocalDataService


WINDOW = 30
MAX_SERIES_DAYS = 700

SYMBOLS: list[str] = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "TSLA",
    "META",
    "GOOGL",
    "JPM",
    "V",
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
]


@dataclass
class SeriesResult:
    symbol: str
    closes: list[float]
    source: str


def _looks_like_inr(symbol: str) -> bool:
    sym = symbol.upper()
    return sym.endswith(".NS") or sym.endswith(".NSE") or sym.endswith(".BSE") or sym.endswith(".BO")


def _alpha_candidates(symbol: str) -> list[str]:
    sym = symbol.upper()
    if sym.endswith(".NS"):
        return [sym.replace(".NS", ".NSE")]
    if sym.endswith(".BO"):
        return [sym.replace(".BO", ".BSE")]
    if "." in sym:
        return [sym]
    suffixes: list[str] = []
    primary = settings.ALPHAVANTAGE_INR_SUFFIX or ""
    if primary:
        suffixes.append(primary)
    for extra in (".BSE", ".NSE"):
        if extra and extra not in suffixes:
            suffixes.append(extra)
    if not suffixes:
        return [sym]
    return [f"{sym}{suffix}" for suffix in suffixes]


def _extract_closes(series: list[dict]) -> list[float]:
    closes = [float(point.get("c", 0.0)) for point in series if point.get("c")]
    return [value for value in closes if value > 0]


def _fetch_finnhub_series(service: FinnhubService, symbol: str, days: int) -> list[float]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    data = service.get_candles(symbol, "D", int(start.timestamp()), int(now.timestamp()))
    if data.get("s") != "ok" or not data.get("c"):
        raise ValueError("Finnhub returned empty candles")
    return [float(value) for value in data["c"] if value]


def _fetch_alpha_series(service: AlphaVantageService, symbol: str) -> list[float]:
    series = service.get_daily_series(symbol, output_size="full")
    return _extract_closes(series)


def _load_series(
    symbol: str,
    finnhub: FinnhubService,
    alpha: AlphaVantageService,
    local_data: LocalDataService,
) -> SeriesResult | None:
    is_inr = _looks_like_inr(symbol)
    currency = "INR" if is_inr else "USD"

    if not is_inr and settings.FINNHUB_API_KEY:
        try:
            closes = _fetch_finnhub_series(finnhub, symbol, MAX_SERIES_DAYS)
            if len(closes) >= WINDOW + 1:
                return SeriesResult(symbol, closes[-MAX_SERIES_DAYS:], "finnhub")
        except Exception:
            pass

    if settings.ALPHAVANTAGE_API_KEY:
        candidates = _alpha_candidates(symbol) if is_inr else [symbol]
        for candidate in candidates:
            try:
                closes = _fetch_alpha_series(alpha, candidate)
                if len(closes) >= WINDOW + 1:
                    return SeriesResult(symbol, closes[-MAX_SERIES_DAYS:], "alpha_vantage")
            except Exception as exc:
                message = str(exc)
                if "rate limit" in message.lower() or "Thank you for using Alpha Vantage" in message:
                    time.sleep(65)
                continue

    closes = _extract_closes(local_data.get_series(symbol, currency, days=MAX_SERIES_DAYS))
    if len(closes) >= WINDOW + 1:
        return SeriesResult(symbol, closes[-MAX_SERIES_DAYS:], "local")
    return None


def _build_dataset(series_list: Iterable[SeriesResult]) -> tuple[np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    targets: list[float] = []

    for series in series_list:
        closes = np.asarray(series.closes, dtype=float)
        if closes.size < WINDOW + 1:
            continue
        for idx in range(WINDOW, closes.size):
            window = closes[idx - WINDOW: idx]
            last = window[-1]
            scale = last if last != 0 else 1.0
            features.append((window / scale).astype(np.float32))
            targets.append(float(closes[idx] / scale))

    if not features:
        raise RuntimeError("No training windows available; check data sources.")

    x = np.stack(features, axis=0)
    y = np.asarray(targets, dtype=np.float32)
    return x, y


def train_model() -> Path:
    from tensorflow import keras  # type: ignore

    finnhub = FinnhubService()
    alpha = AlphaVantageService()
    local_data = LocalDataService()

    series_results: list[SeriesResult] = []
    for symbol in SYMBOLS:
        result = _load_series(symbol, finnhub, alpha, local_data)
        if result:
            print(f"Loaded {result.symbol} from {result.source}: {len(result.closes)} closes")
            series_results.append(result)
        else:
            print(f"Skipped {symbol}: insufficient data")

    x, y = _build_dataset(series_results)
    x = x.reshape(x.shape[0], x.shape[1], 1)

    rng = np.random.default_rng(42)
    indices = rng.permutation(len(x))
    x = x[indices]
    y = y[indices]

    split = int(len(x) * 0.9)
    x_train, x_val = x[:split], x[split:]
    y_train, y_val = y[:split], y[split:]

    model = keras.Sequential(
        [
            keras.layers.Input(shape=(WINDOW, 1)),
            keras.layers.LSTM(48, dropout=0.1),
            keras.layers.Dense(24, activation="relu"),
            keras.layers.Dense(1),
        ]
    )
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss=keras.losses.Huber(),
        metrics=[keras.metrics.MeanAbsolutePercentageError()],
    )

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=4,
            restore_best_weights=True,
        )
    ]

    model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val) if len(x_val) else None,
        epochs=20,
        batch_size=64,
        callbacks=callbacks,
        verbose=1,
    )

    artifacts_dir = Path(__file__).resolve().parent / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / "lstm_stock_price.h5"
    model.save(model_path)
    print(f"Saved model to {model_path}")
    return model_path


if __name__ == "__main__":
    trained_path = train_model()
    print(f"Training complete: {trained_path}")
