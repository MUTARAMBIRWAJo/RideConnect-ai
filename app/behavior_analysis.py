"""behavior_analysis.py — Driver performance classification.

Uses a RandomForestClassifier to label drivers as:
    safe | efficient | risky | inefficient

Features:
    [avg_trip_duration_min, avg_speed_kmh, cancellation_rate,
     avg_rating, route_deviation_pct, total_rides_normalised]

Model is bootstrapped with synthetic data and retrained when real
driver_behavior_logs data accumulates.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import joblib
import numpy as np

from app.utils import logger

BEHAVIOR_MODEL_PATH = os.environ.get("BEHAVIOR_MODEL_PATH", "models/behavior_model.pkl")
CLASSES = ["safe", "efficient", "risky", "inefficient"]


class BehaviorAnalyzer:
    def __init__(self, path: str = BEHAVIOR_MODEL_PATH) -> None:
        self._model = None
        self._path = path

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if os.path.exists(self._path):
            try:
                self._model = joblib.load(self._path)
                logger.info("Behavior model loaded from %s", self._path)
                return
            except Exception as exc:
                logger.warning("Could not load behavior model: %s")
        self._bootstrap()

    def _bootstrap(self) -> None:
        from sklearn.ensemble import RandomForestClassifier

        rng = np.random.default_rng(21)
        n = 400

        # Synthetic driver profiles
        dur = rng.uniform(5, 90, n)       # avg trip duration minutes
        spd = rng.uniform(10, 80, n)      # avg speed km/h
        cancel = rng.uniform(0, 0.4, n)   # cancellation rate
        rating = rng.uniform(2.5, 5.0, n)
        deviation = rng.uniform(0, 30, n) # route deviation %
        total = rng.uniform(0, 1, n)      # total rides normalised

        # Labelling heuristics
        labels = []
        for i in range(n):
            if cancel[i] > 0.25 or deviation[i] > 20:
                labels.append("risky")
            elif rating[i] < 3.0 or dur[i] > 70:
                labels.append("inefficient")
            elif spd[i] > 55 or deviation[i] > 10:
                labels.append("efficient")
            else:
                labels.append("safe")

        X = np.column_stack([dur, spd, cancel, rating, deviation, total])
        y = np.array(labels)

        self._model = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
        self._model.fit(X, y)
        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        joblib.dump(self._model, self._path)
        logger.info("Behavior model bootstrapped → %s", self._path)

    def classify(
        self,
        avg_trip_duration_min: float,
        avg_speed_kmh: float,
        cancellation_rate: float,
        avg_rating: float,
        route_deviation_pct: float = 5.0,
        total_rides: int = 50,
    ) -> Dict[str, Any]:
        total_norm = min(1.0, total_rides / 1000.0)
        X = np.array([[avg_trip_duration_min, avg_speed_kmh, cancellation_rate,
                       avg_rating, route_deviation_pct, total_norm]])

        if self._model is None:
            # Heuristic fallback
            if cancellation_rate > 0.25:
                label = "risky"
            elif avg_rating < 3.0:
                label = "inefficient"
            elif avg_speed_kmh > 55:
                label = "efficient"
            else:
                label = "safe"
            return {"behavior_class": label, "confidence": 0.50, "probabilities": {}}

        try:
            label = str(self._model.predict(X)[0])
            probs = {c: round(float(p), 4)
                     for c, p in zip(self._model.classes_, self._model.predict_proba(X)[0])}
            confidence = round(max(probs.values()), 4)
            return {
                "behavior_class": label,
                "confidence": confidence,
                "probabilities": probs,
            }
        except Exception as exc:
            logger.error("Behavior classify error: %s", exc)
            return {"behavior_class": "unknown", "confidence": 0.0, "probabilities": {}}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_analyzer: Optional[BehaviorAnalyzer] = None


def get_analyzer() -> BehaviorAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = BehaviorAnalyzer()
        _analyzer.load()
    return _analyzer
