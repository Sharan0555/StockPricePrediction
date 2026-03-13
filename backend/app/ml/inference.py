from __future__ import annotations

from typing import Dict, List

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
        window = min(20, returns.size)
        mean_return = float(np.mean(returns[-window:])) if window > 0 else 0.0
        mean_return = float(np.clip(mean_return, -0.02, 0.02))
        return last * (1 + mean_return)

    def _sanitize_prediction(self, predicted: float, last: float, fallback: float) -> float:
        if not np.isfinite(predicted) or predicted <= 0:
            return fallback
        # If prediction is wildly off (e.g., untrained model), use fallback.
        if predicted < last * 0.7 or predicted > last * 1.3:
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

        # Lazy-load LSTM model to avoid heavy startup / OOM in Docker.
        if self._lstm_model is None and not settings.LOCAL_DATA_ONLY:
            try:
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
            lstm_pred = self._sanitize_prediction(raw_pred, last, baseline_pred)

        ensemble_pred = lstm_pred
        return {
            "lstm": lstm_pred,
            "ensemble": ensemble_pred,
        }


prediction_engine = PredictionEngine()
