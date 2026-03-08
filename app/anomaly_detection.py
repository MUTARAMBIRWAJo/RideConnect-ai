"""anomaly_detection.py — Fare anomaly detection.

Techniques:
    1. IsolationForest — density-based outlier detection
    2. Z-score — statistical outlier flag

Detects:
    double_pricing      — fare >> expected for distance
    abnormal_surge      — demand multiplier unusually high
    unusual_distance    — trip distance inconsistent with fare
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import joblib
import numpy as np

from app.utils import logger

ANOMALY_MODEL_PATH = os.environ.get("ANOMALY_MODEL_PATH", "models/anomaly_model.pkl")
Z_THRESHOLD = 3.0   # standard deviations


class FareAnomalyDetector:
    def __init__(self, path: str = ANOMALY_MODEL_PATH) -> None:
        self._iso = None
        self._path = path
        self._fare_mean: float = 3000.0
        self._fare_std: float = 2000.0

    @property
    def is_loaded(self) -> bool:
        return self._iso is not None

    def load(self) -> None:
        if os.path.exists(self._path):
            try:
                saved = joblib.load(self._path)
                self._iso = saved["iso"]
                self._fare_mean = saved.get("mean", 3000.0)
                self._fare_std = saved.get("std", 2000.0)
                logger.info("Anomaly detection model loaded from %s", self._path)
                return
            except Exception as exc:
                logger.warning("Could not load anomaly model: %s", exc)
        self._bootstrap()

    def _bootstrap(self) -> None:
        from sklearn.ensemble import IsolationForest

        rng = np.random.default_rng(55)
        n = 500
        dist = rng.uniform(1, 80, n)
        fare = 800 + dist * 180 + rng.normal(0, 300, n)
        # Inject anomalies
        idx = rng.choice(n, 20, replace=False)
        fare[idx] *= rng.uniform(2.5, 5.0, 20)

        X = np.column_stack([dist, fare, fare / np.maximum(dist, 0.1)])
        self._iso = IsolationForest(contamination=0.05, random_state=42)
        self._iso.fit(X)
        self._fare_mean = float(np.mean(fare))
        self._fare_std = float(np.std(fare))

        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        joblib.dump({"iso": self._iso, "mean": self._fare_mean, "std": self._fare_std}, self._path)
        logger.info("Anomaly model bootstrapped → %s", self._path)

    def detect(
        self,
        fare: float,
        distance_km: float,
        demand_level: int = 3,
    ) -> Dict[str, Any]:
        fare_per_km = fare / max(distance_km, 0.1)
        X = np.array([[distance_km, fare, fare_per_km]])

        # --- IsolationForest score ---
        iso_flag = False
        iso_score = 0.0
        if self._iso is not None:
            try:
                pred = self._iso.predict(X)[0]  # -1 = outlier, 1 = normal
                iso_score = round(float(-self._iso.score_samples(X)[0]), 4)
                iso_flag = (pred == -1)
            except Exception as exc:
                logger.warning("IsolationForest predict error: %s", exc)

        # --- Z-score ---
        z = (fare - self._fare_mean) / max(self._fare_std, 1.0)
        z_flag = abs(z) > Z_THRESHOLD

        anomaly = iso_flag or z_flag

        # Classify anomaly type
        anomaly_type = None
        if anomaly:
            expected = 800 + distance_km * 180
            if fare > expected * 2.5:
                anomaly_type = "abnormal_surge"
            elif fare_per_km > 500:
                anomaly_type = "double_pricing"
            elif distance_km > 80 and fare < 1000:
                anomaly_type = "unusual_distance"
            else:
                anomaly_type = "general_outlier"

        return {
            "anomaly_detected": bool(anomaly),
            "anomaly_type": anomaly_type,
            "anomaly_score": float(iso_score),
            "z_score": round(float(z), 4),
            "fare_per_km": round(float(fare_per_km), 2),
            "iso_flag": bool(iso_flag),
            "z_score_flag": bool(z_flag),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_detector: Optional[FareAnomalyDetector] = None


def get_anomaly_detector() -> FareAnomalyDetector:
    global _detector
    if _detector is None:
        _detector = FareAnomalyDetector()
        _detector.load()
    return _detector
