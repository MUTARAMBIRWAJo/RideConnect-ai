"""eta_predictor.py — Travel-time (ETA) prediction.

Uses GradientBoostingRegressor trained on features:
    [distance_km, traffic_level, hour, day_of_week,
     road_type_enc, weather_enc, historical_duration_avg]

Falls back to a speed-heuristic formula when model is not loaded.
"""

from __future__ import annotations

import datetime
import os
from typing import Optional

import joblib
import numpy as np

from app.utils import logger

ETA_MODEL_PATH = os.environ.get("ETA_MODEL_PATH", "models/eta_model.pkl")

ROAD_TYPE_ENC = {"highway": 0, "main_road": 1, "local": 2, "dirt": 3}
WEATHER_ENC = {"clear": 0, "cloudy": 1, "rain": 2, "heavy_rain": 3, "fog": 4}
TRAFFIC_SPEED = {1: 55, 2: 45, 3: 32, 4: 20, 5: 12}  # km/h averages


class ETAPredictor:
    def __init__(self, path: str = ETA_MODEL_PATH) -> None:
        self._model = None
        self._path = path

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if os.path.exists(self._path):
            try:
                self._model = joblib.load(self._path)
                logger.info("ETA model loaded from %s", self._path)
                return
            except Exception as exc:
                logger.warning("Could not load ETA model: %s", exc)
        self._bootstrap()

    def _bootstrap(self) -> None:
        from sklearn.ensemble import GradientBoostingRegressor

        rng = np.random.default_rng(17)
        n = 600
        dist = rng.uniform(0.5, 80, n)
        traffic = rng.integers(1, 6, n).astype(float)
        hour = rng.integers(0, 24, n).astype(float)
        dow = rng.integers(0, 7, n).astype(float)
        road = rng.integers(0, 4, n).astype(float)
        weather = rng.integers(0, 5, n).astype(float)
        hist_dur = 2 + dist * 1.5 + rng.normal(0, 2, n)

        base_speed = np.array([TRAFFIC_SPEED.get(int(t), 30) for t in traffic], dtype=float)
        weather_penalty = np.array([1.0, 1.05, 1.20, 1.40, 1.15])[weather.astype(int)]
        road_penalty = np.array([0.85, 1.0, 1.25, 1.60])[road.astype(int)]
        y = (dist / (base_speed * road_penalty * (1 / weather_penalty))) * 60
        y += rng.normal(0, 1.5, n)
        y = np.clip(y, 1, 300)

        X = np.column_stack([dist, traffic, hour, dow, road, weather, hist_dur])
        self._model = GradientBoostingRegressor(n_estimators=150, max_depth=5, random_state=42)
        self._model.fit(X, y)
        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        joblib.dump(self._model, self._path)
        logger.info("ETA model bootstrapped → %s", self._path)

    def predict(
        self,
        distance_km: float,
        traffic_level: int,
        hour: Optional[int] = None,
        day_of_week: Optional[int] = None,
        road_type: str = "main_road",
        weather: str = "clear",
        historical_duration_avg: Optional[float] = None,
    ) -> float:
        now = datetime.datetime.now()
        hour = hour if hour is not None else now.hour
        day_of_week = day_of_week if day_of_week is not None else now.weekday()
        road_enc = ROAD_TYPE_ENC.get(road_type.lower(), 1)
        weather_enc = WEATHER_ENC.get(weather.lower(), 0)
        hist = historical_duration_avg if historical_duration_avg is not None else distance_km * 1.8

        if self._model is None:
            # Pure heuristic fallback
            speed = TRAFFIC_SPEED.get(traffic_level, 30)
            return round((distance_km / speed) * 60, 1)

        X = np.array([[distance_km, traffic_level, hour, day_of_week,
                       road_enc, weather_enc, hist]])
        try:
            return round(max(1.0, float(self._model.predict(X)[0])), 1)
        except Exception as exc:
            logger.warning("ETA model predict error: %s", exc)
            speed = TRAFFIC_SPEED.get(traffic_level, 30)
            return round((distance_km / speed) * 60, 1)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_eta_predictor: Optional[ETAPredictor] = None


def get_eta_predictor() -> ETAPredictor:
    global _eta_predictor
    if _eta_predictor is None:
        _eta_predictor = ETAPredictor()
        _eta_predictor.load()
    return _eta_predictor
