"""Demand model adapter for AI intelligence endpoints.

This module reuses the existing demand predictor (LSTM when available, RF fallback)
and normalizes outputs for the new /ai endpoints.
"""

from __future__ import annotations

import datetime
from typing import Dict, Optional

from app.demand_prediction import get_predictor


class DemandLSTMModel:
    """Adapter around the existing demand predictor singleton."""

    def __init__(self) -> None:
        self._predictor = get_predictor()

    def predict_next_window(
        self,
        lat: float,
        lng: float,
        historical_count: int,
        weather: str = "clear",
        hour: Optional[int] = None,
        day_of_week: Optional[int] = None,
        traffic_level: int = 3,
        event_indicator: int = 0,
    ) -> Dict[str, float]:
        now = datetime.datetime.now()
        h = now.hour if hour is None else hour
        dow = now.weekday() if day_of_week is None else day_of_week

        prediction = self._predictor.predict(
            hour=h,
            day_of_week=dow,
            traffic_level=traffic_level,
            historical_count=max(1, int(historical_count)),
            lat=lat,
            lng=lng,
            weather=weather,
            event_indicator=event_indicator,
        )
        return {
            "demand_score": float(prediction["demand_score"]),
            "expected_rides": int(prediction["predicted_requests"]),
            "confidence": float(prediction["confidence"]),
        }


_model: Optional[DemandLSTMModel] = None


def get_demand_lstm_model() -> DemandLSTMModel:
    global _model
    if _model is None:
        _model = DemandLSTMModel()
    return _model
