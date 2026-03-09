"""Cancellation anomaly model for suspicious driver behavior."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from app.utils import logger

CANCELLATION_MODEL_PATH = os.environ.get(
    "CANCELLATION_MODEL_PATH",
    "models/cancellation_anomaly.pkl",
)


class CancellationAnomalyModel:
    def __init__(self, path: str = CANCELLATION_MODEL_PATH) -> None:
        self._path = path
        self._model: Optional[IsolationForest] = None

    def load(self) -> None:
        if os.path.exists(self._path):
            try:
                self._model = joblib.load(self._path)
                return
            except Exception as exc:
                logger.warning("Failed loading cancellation model: %s", exc)
        self._bootstrap()

    def _bootstrap(self) -> None:
        rng = np.random.default_rng(123)
        n = 450
        accepted = rng.integers(20, 320, n)
        cancelled = rng.integers(0, 40, n)
        time_to_cancel = rng.uniform(0.3, 6.0, n)
        complaints = rng.integers(0, 4, n)

        # Inject anomalous behavior
        for idx in rng.choice(n, 40, replace=False):
            cancelled[idx] = min(accepted[idx], int(accepted[idx] * rng.uniform(0.3, 0.7)))
            time_to_cancel[idx] = rng.uniform(0.1, 1.5)
            complaints[idx] = rng.integers(3, 10)

        rates = cancelled / np.maximum(accepted, 1)
        X = np.column_stack([accepted, cancelled, rates, time_to_cancel, complaints])
        model = IsolationForest(contamination=0.1, random_state=42)
        model.fit(X)

        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        joblib.dump(model, self._path)
        self._model = model

    def detect(self, rows: List[Dict]) -> List[Dict]:
        if self._model is None:
            self.load()
        if not rows or self._model is None:
            return []

        X = []
        for r in rows:
            accepted = max(int(r.get("rides_accepted", 0)), 1)
            cancelled = max(int(r.get("rides_cancelled", 0)), 0)
            rate = cancelled / accepted
            ttc = float(r.get("time_to_cancel", 0.0))
            complaints = int(r.get("passenger_complaints", 0))
            X.append([accepted, cancelled, rate, ttc, complaints])

        feats = np.asarray(X, dtype=float)
        preds = self._model.predict(feats)

        anomalies = []
        for i, pred in enumerate(preds):
            if pred != -1:
                continue
            row = rows[i]
            accepted = max(int(row.get("rides_accepted", 0)), 1)
            cancelled = max(int(row.get("rides_cancelled", 0)), 0)
            rate = round(cancelled / accepted, 4)
            risk_level = "high" if rate >= 0.35 else ("medium" if rate >= 0.2 else "low")
            anomalies.append(
                {
                    "driver_id": row.get("driver_id"),
                    "cancellation_rate": rate,
                    "risk_level": risk_level,
                    "reason": "Cancellation rate exceeds system threshold",
                }
            )
        return anomalies


_model: Optional[CancellationAnomalyModel] = None


def get_cancellation_anomaly_model() -> CancellationAnomalyModel:
    global _model
    if _model is None:
        _model = CancellationAnomalyModel()
        _model.load()
    return _model
