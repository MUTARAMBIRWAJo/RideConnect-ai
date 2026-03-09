"""Inference wrapper for zone demand forecasting."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from algorithms.demand.zone_forecasting import forecast_zone_demand
from utils.storage import load_json_weights, save_json_weights


class DemandModel:
    def __init__(self) -> None:
        payload = load_json_weights("demand_weights.json", {"zone_history": {}})
        self.zone_history: Dict[str, List[float]] = defaultdict(list)
        for zone, hist in payload.get("zone_history", {}).items():
            self.zone_history[zone] = [float(v) for v in hist]

    def update_observation(self, zone: str, observed_requests: float) -> None:
        hist = self.zone_history[zone]
        hist.append(float(observed_requests))
        if len(hist) > 120:
            del hist[:-120]

    def predict(self, zone: str, hour: int, is_weekend: bool, weather_factor: float = 1.0) -> Dict:
        series = list(self.zone_history.get(zone, []))
        if not series:
            series = [8.0, 10.0, 11.0, 9.0, 12.0]

        # Temporal correction with weekend and hour demand shape.
        hour_factor = 1.18 if (7 <= hour <= 9 or 17 <= hour <= 20) else 0.95
        weekend_factor = 0.92 if is_weekend else 1.05

        raw = forecast_zone_demand({zone: series})[zone]
        predicted_requests = raw["predicted_requests_per_zone"] * hour_factor * weekend_factor * weather_factor
        supply_needed = predicted_requests * 0.72

        return {
            "zone": zone,
            "predicted_requests_per_zone": round(predicted_requests, 2),
            "predicted_driver_supply_needed": round(supply_needed, 2),
        }

    def save(self) -> str:
        return save_json_weights("demand_weights.json", {"zone_history": dict(self.zone_history)})
