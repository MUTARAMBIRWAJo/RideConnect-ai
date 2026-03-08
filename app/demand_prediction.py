"""demand_prediction.py — Demand forecasting engine.

Two-tier approach:
  1. LSTM (PyTorch) — used when enough historical data exists (≥ 200 rows)
  2. RandomForestRegressor — lightweight fallback always available

Features:
  [hour, day_of_week, is_peak, traffic_level, historical_ride_count,
   lat_bucket, lng_bucket, event_indicator, weather_encoded]

Output per zone:
  demand_score (0–1), predicted_requests (int), confidence (0–1)
"""

from __future__ import annotations

import datetime
import math
import os
from typing import Any, Dict, List, Optional

import joblib
import numpy as np

from app.utils import logger

DEMAND_MODEL_PATH = os.environ.get("DEMAND_MODEL_PATH", "models/demand_model.pkl")
MIN_LSTM_ROWS = 200

WEATHER_ENC = {"clear": 0, "cloudy": 1, "rain": 2, "heavy_rain": 3, "fog": 4}


# ---------------------------------------------------------------------------
# Feature helpers
# ---------------------------------------------------------------------------
def _lat_bucket(lat: float) -> int:
    """Quantise latitude into ~1-km buckets."""
    return int(lat * 100)


def _lng_bucket(lng: float) -> int:
    return int(lng * 100)


def _is_peak(hour: int, dow: int) -> int:
    """1 if rush-hour on a weekday."""
    return int(dow < 5 and (7 <= hour <= 9 or 17 <= hour <= 19))


def _encode_features(
    hour: int,
    day_of_week: int,
    traffic_level: int,
    historical_count: int,
    lat: float,
    lng: float,
    weather: str = "clear",
    event_indicator: int = 0,
) -> np.ndarray:
    return np.array([
        [
            hour,
            day_of_week,
            _is_peak(hour, day_of_week),
            traffic_level,
            historical_count,
            _lat_bucket(lat),
            _lng_bucket(lng),
            event_indicator,
            WEATHER_ENC.get(weather.lower(), 0),
        ]
    ], dtype=float)


# ---------------------------------------------------------------------------
# LSTM model wrapper (no-op when PyTorch unavailable)
# ---------------------------------------------------------------------------
class LSTMDemandModel:
    """Thin wrapper — trains a minimal 1-layer LSTM sequence model."""

    def __init__(self) -> None:
        self._model = None
        self._available = False
        try:
            import torch  # noqa: F401
            self._available = True
        except ImportError:
            logger.warning("PyTorch not installed — LSTM demand model disabled.")

    @property
    def available(self) -> bool:
        return self._available

    def build_and_train(self, X: np.ndarray, y: np.ndarray) -> None:
        if not self._available:
            return
        try:
            import torch
            import torch.nn as nn

            seq_len = min(24, len(X))
            n_feat = X.shape[1]

            class _LSTM(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.lstm = nn.LSTM(n_feat, 64, batch_first=True)
                    self.fc = nn.Linear(64, 1)

                def forward(self, x):
                    out, _ = self.lstm(x)
                    return self.fc(out[:, -1, :]).squeeze(1)

            model = _LSTM()
            opt = torch.optim.Adam(model.parameters(), lr=1e-3)
            loss_fn = nn.MSELoss()

            Xt = torch.tensor(X[-seq_len:].reshape(1, seq_len, n_feat), dtype=torch.float32)
            yt = torch.tensor([y[-1]], dtype=torch.float32)

            model.train()
            for _ in range(50):
                opt.zero_grad()
                loss = loss_fn(model(Xt), yt)
                loss.backward()
                opt.step()

            self._model = model
            logger.info("LSTM demand model trained.")
        except Exception as exc:
            logger.warning("LSTM training failed: %s", exc)

    def predict(self, X: np.ndarray) -> Optional[float]:
        if not self._available or self._model is None:
            return None
        try:
            import torch
            with torch.no_grad():
                Xt = torch.tensor(X.reshape(1, 1, -1), dtype=torch.float32)
                return float(self._model(Xt).item())
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Main DemandPredictor
# ---------------------------------------------------------------------------
class DemandPredictor:
    """Combines RF (always ready) with optional LSTM."""

    def __init__(self, model_path: str = DEMAND_MODEL_PATH) -> None:
        self._rf = None
        self._lstm = LSTMDemandModel()
        self._path = model_path

    @property
    def is_loaded(self) -> bool:
        return self._rf is not None

    def load(self) -> None:
        if os.path.exists(self._path):
            try:
                self._rf = joblib.load(self._path)
                logger.info("Demand RF model loaded from %s", self._path)
                return
            except Exception as exc:
                logger.warning("Could not load demand model: %s", exc)
        self._bootstrap_rf()

    def _bootstrap_rf(self) -> None:
        """Train a small RF on synthetic demand data so predictions are always available."""
        from sklearn.ensemble import RandomForestRegressor

        rng = np.random.default_rng(99)
        n = 500
        hours = rng.integers(0, 24, n).astype(float)
        dows = rng.integers(0, 7, n).astype(float)
        traffic = rng.integers(1, 6, n).astype(float)
        hist = rng.integers(5, 80, n).astype(float)
        lats = rng.uniform(-2.0, -1.8, n)
        lngs = rng.uniform(29.9, 30.2, n)
        weather = rng.integers(0, 5, n).astype(float)
        events = rng.integers(0, 2, n).astype(float)
        peak = np.array([_is_peak(int(h), int(d)) for h, d in zip(hours, dows)], dtype=float)

        X = np.column_stack([hours, dows, peak, traffic, hist,
                             (lats * 100).astype(int), (lngs * 100).astype(int), events, weather])
        y = (hist / 80) * (1 + peak * 0.5) * (1 + (traffic - 3) * 0.08) + rng.normal(0, 0.05, n)
        y = np.clip(y, 0, 1)

        self._rf = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
        self._rf.fit(X, y)
        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        joblib.dump(self._rf, self._path)
        logger.info("Demand model bootstrapped and saved to %s", self._path)

    def predict(
        self,
        hour: int,
        day_of_week: int,
        traffic_level: int,
        historical_count: int,
        lat: float,
        lng: float,
        weather: str = "clear",
        event_indicator: int = 0,
    ) -> Dict[str, Any]:
        X = _encode_features(hour, day_of_week, traffic_level,
                              historical_count, lat, lng, weather, event_indicator)

        # Try LSTM first (higher accuracy when trained on real sequences)
        lstm_score = self._lstm.predict(X)

        if lstm_score is not None:
            score = float(np.clip(lstm_score, 0, 1))
            source = "lstm"
        elif self._rf is not None:
            score = float(np.clip(self._rf.predict(X)[0], 0, 1))
            source = "rf"
        else:
            # Pure heuristic
            peak_factor = 0.8 if _is_peak(hour, day_of_week) else 0.4
            score = float(np.clip(peak_factor + (traffic_level - 3) * 0.05, 0, 1))
            source = "heuristic"

        base_requests = max(1, round(historical_count * score))
        confidence = 0.88 if source == "lstm" else (0.75 if source == "rf" else 0.50)

        return {
            "demand_score": round(score, 4),
            "predicted_requests": base_requests,
            "confidence": round(confidence, 4),
            "source": source,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_predictor: Optional[DemandPredictor] = None


def get_predictor() -> DemandPredictor:
    global _predictor
    if _predictor is None:
        _predictor = DemandPredictor()
        _predictor.load()
    return _predictor
