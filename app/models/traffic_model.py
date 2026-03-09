"""Traffic model utilities for route monitoring endpoints."""

from __future__ import annotations

import datetime
from typing import Dict


class TrafficModel:
    """Lightweight traffic estimator based on time-of-day heuristics."""

    def estimate(self, distance_km: float) -> Dict[str, float]:
        now = datetime.datetime.now()
        hour = now.hour

        if 7 <= hour <= 9 or 17 <= hour <= 20:
            congestion_factor = 1.45
        elif 10 <= hour <= 16:
            congestion_factor = 1.2
        else:
            congestion_factor = 1.05

        baseline_minutes = (distance_km / 32.0) * 60.0
        actual_minutes = baseline_minutes * congestion_factor
        delay_minutes = max(0.0, actual_minutes - baseline_minutes)

        return {
            "baseline_minutes": round(baseline_minutes, 2),
            "traffic_minutes": round(actual_minutes, 2),
            "delay_minutes": round(delay_minutes, 2),
            "congestion_factor": round(congestion_factor, 2),
        }


_model = TrafficModel()


def get_traffic_model() -> TrafficModel:
    return _model
