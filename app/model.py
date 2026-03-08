"""model.py — PriceModel wrapper.

Loads a pre-trained RandomForest from disk.  If the model file is missing the
service degrades gracefully using a rule-based fallback so the container
stays healthy and can serve requests while training is in progress.

Feature vector (order must match train_model.py):
    [distance_km, demand_level, traffic_level, ride_type_enc, hour, day_of_week]
"""

import datetime
import math
import os
from typing import Optional

import joblib
import numpy as np

from app.utils import logger

# ---------------------------------------------------------------------------
# Ride-type encoding — must stay in sync with app/train_model.py
# ---------------------------------------------------------------------------
RIDE_TYPE_MAP = {"standard": 0, "premium": 1, "boda": 2, "shared": 3}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres between two coordinates."""
    R = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin(math.radians(lat2 - lat1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return round(2 * R * math.asin(math.sqrt(max(a, 0.0))), 3)


class PriceModel:
    """Singleton wrapper around a persisted sklearn model."""

    BASE_PRICE: float = 1_000.0  # KES fallback base

    def __init__(self, path: str) -> None:
        self.path = path
        self._model = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if os.path.exists(self.path):
            try:
                self._model = joblib.load(self.path)
                logger.info("Model loaded from %s", self.path)
            except Exception as exc:
                logger.error("Failed to load model from %s: %s", self.path, exc)
                self._model = None
        else:
            logger.warning(
                "Model file not found at '%s'. Predictions will use rule-based fallback "
                "until train_model.py is run.",
                self.path,
            )

    def predict(
        self,
        distance_km: float,
        demand_level: int,
        traffic_level: int,
        ride_type: str = "standard",
        hour: Optional[int] = None,
        day_of_week: Optional[int] = None,
    ) -> float:
        now = datetime.datetime.now()
        hour = hour if hour is not None else now.hour
        day_of_week = day_of_week if day_of_week is not None else now.weekday()
        ride_type_enc = RIDE_TYPE_MAP.get(ride_type.lower().strip(), 0)

        if not self.is_loaded:
            # Rule-based fallback prices calibrated for East-African market (KES)
            base = self.BASE_PRICE + distance_km * 200
            surge = 1.0 + (demand_level - 1) * 0.15 + (traffic_level - 1) * 0.08
            type_premium = [0, 400, 200, -100][ride_type_enc]
            return round((base * surge) + type_premium, 2)

        features = np.array(
            [[distance_km, demand_level, traffic_level, ride_type_enc, hour, day_of_week]]
        )
        try:
            return round(float(self._model.predict(features)[0]), 2)
        except Exception as exc:
            logger.error("Model prediction error: %s", exc)
            return round(self.BASE_PRICE + distance_km * 200, 2)
