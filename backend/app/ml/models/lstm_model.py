from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


MODEL_DIR = Path(__file__).resolve().parent.parent / "artifacts"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "lstm_stock_price.h5"


class LSTMStockModel:
    def __init__(self) -> None:
        # Import TensorFlow lazily to avoid heavy startup / OOM in constrained environments.
        from tensorflow import keras  # type: ignore

        self._keras = keras
        if MODEL_PATH.exists():
            self.model = keras.models.load_model(MODEL_PATH)
        else:
            self.model = self._build_dummy_model()

    def _build_dummy_model(self):
        keras = self._keras
        inputs = keras.Input(shape=(30, 1))
        x = keras.layers.LSTM(32)(inputs)
        outputs = keras.layers.Dense(1)(x)
        model = keras.Model(inputs=inputs, outputs=outputs)
        model.compile(optimizer="adam", loss="mse")
        return model

    def predict_sequence(self, series: np.ndarray) -> float:
        if series.ndim == 1:
            series = series.reshape(1, -1, 1)
        elif series.ndim == 2:
            series = series.reshape(series.shape[0], series.shape[1], 1)
        preds: Any = self.model.predict(series, verbose=0)
        return float(preds[0][0])

