from __future__ import annotations

from typing import Dict, List
from pathlib import Path

import numpy as np

from app.core.config import settings

class PredictionEngine:
    def __init__(self) -> None:
        self._lstm_model = None

    def _prepare_window(self, series: np.ndarray, window: int = 30) -> np.ndarray:
        series = np.ravel(series)
        if series.size >= window:
            return series[-window:]
        # Pad with the last known value to reach the required window length.
        pad_value = float(series[-1]) if series.size > 0 else 0.0
        return np.pad(series, (window - series.size, 0), mode="constant", constant_values=pad_value)

    def _baseline_prediction(self, series: np.ndarray) -> float:
        if series.size == 0:
            return 0.0
        last = float(series[-1])
        if series.size < 2:
            return last
        returns = np.diff(series) / series[:-1]
        window = min(30, returns.size)
        recent = returns[-window:] if window > 0 else returns
        if recent.size == 0:
            return last

        # Weighted mean of recent returns (emphasize latest points).
        weights = np.linspace(0.4, 1.0, recent.size)
        weighted_mean = float(np.average(recent, weights=weights))

        # Linear trend (slope) on recent closes to capture short-term drift.
        closes_window = series[-(window + 1):] if series.size > window else series
        x = np.arange(closes_window.size, dtype=float)
        x_mean = float(np.mean(x))
        y_mean = float(np.mean(closes_window))
        denom = float(np.sum((x - x_mean) ** 2))
        slope = float(np.sum((x - x_mean) * (closes_window - y_mean)) / denom) if denom else 0.0
        slope_return = slope / last if last else 0.0

        # Mean reversion toward 20-period SMA to avoid drift overshoot.
        sma_window = series[-min(20, series.size):]
        sma = float(np.mean(sma_window))
        mean_reversion = (sma - last) / last if last else 0.0

        blended_return = (0.55 * weighted_mean) + (0.25 * slope_return) + (0.20 * mean_reversion)

        vol = float(np.std(recent)) if recent.size else 0.0
        max_move = min(0.02, max(0.003, vol * 2.0))
        blended_return = float(np.clip(blended_return, -max_move, max_move))
        return last * (1 + blended_return)

    def _sanitize_prediction(self, predicted: float, last: float, fallback: float, vol: float) -> float:
        if not np.isfinite(predicted) or predicted <= 0:
            return fallback
        # If prediction is wildly off (e.g., untrained model), use fallback.
        max_move = min(0.03, max(0.005, vol * 2.5))
        if predicted < last * (1 - max_move) or predicted > last * (1 + max_move):
            return fallback
        return predicted

    def predict_next_price(self, closes: List[float]) -> Dict[str, float]:
        series = np.asarray(closes, dtype=float)
        if series.ndim > 1:
            series = np.ravel(series)
        if series.size == 0:
            raise ValueError("closes must contain at least one price")

        last = float(series[-1])
        baseline_pred = self._baseline_prediction(series)
        returns = np.diff(series) / series[:-1] if series.size > 1 else np.array([0.0])
        recent_returns = returns[-30:] if returns.size > 30 else returns
        vol = float(np.std(recent_returns)) if recent_returns.size > 0 else 0.0

        # Lazy-load LSTM model to avoid heavy startup / OOM in Docker.
        if self._lstm_model is None and not settings.LOCAL_DATA_ONLY:
            try:
                model_path = (
                    Path(__file__).resolve().parent / "artifacts" / "lstm_stock_price.h5"
                )
                if not model_path.exists():
                    raise FileNotFoundError("LSTM model artifact is missing.")
                from app.ml.models.lstm_model import LSTMStockModel

                self._lstm_model = LSTMStockModel()
            except Exception:
                self._lstm_model = "unavailable"
        elif settings.LOCAL_DATA_ONLY:
            self._lstm_model = "unavailable"

        window = self._prepare_window(series, window=30)

        if self._lstm_model == "unavailable":
            # Safe fallback: naive prediction = last value
            lstm_pred = baseline_pred
        else:
            raw_pred = self._lstm_model.predict_sequence(window)  # type: ignore[union-attr]
            lstm_pred = self._sanitize_prediction(raw_pred, last, baseline_pred, vol)

        # Blend model output with robust baseline for stability.
        ensemble_pred = (0.7 * baseline_pred) + (0.3 * lstm_pred)

        # Final clamp to realistic daily move based on recent volatility.
        expected_move = min(0.01, max(0.003, vol * 2.0))
        lower = last * (1 - expected_move)
        upper = last * (1 + expected_move)
        ensemble_pred = float(np.clip(ensemble_pred, lower, upper))
        return {
            "lstm": lstm_pred,
            "ensemble": ensemble_pred,
        }


prediction_engine = PredictionEngine()
