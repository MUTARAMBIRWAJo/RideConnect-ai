"""Inference wrapper for ETA prediction."""

from __future__ import annotations

from typing import Dict, List

from algorithms.eta.route_estimator import estimate_eta_minutes, estimate_route_distance_km
from algorithms.eta.traffic_adjustment import corrected_eta_minutes
from algorithms.pricing.regression_model import LinearRegressionGD
from utils.storage import load_json_weights, save_json_weights


class ETAModel:
    def __init__(self) -> None:
        payload = load_json_weights(
            "eta_weights.json",
            {
                "linear": {"weights": [0.0, 0.0, 0.0, 0.0], "bias": 0.0},
                "default_speed_kmh": 28.0,
            },
        )
        self.linear = LinearRegressionGD.from_dict(payload.get("linear", {}))
        self.default_speed_kmh = float(payload.get("default_speed_kmh", 28.0))

    def predict_eta(self, features: Dict) -> float:
        distance_km = float(features.get("distance_km") or estimate_route_distance_km(
            float(features["origin_lat"]),
            float(features["origin_lng"]),
            float(features["destination_lat"]),
            float(features["destination_lng"]),
        ))
        traffic_level = float(features.get("traffic_level", 0.4))
        hour = int(features.get("time_of_day", 12))
        road_speed = float(features.get("road_speed_kmh", self.default_speed_kmh))
        hist_travel_time = float(features.get("historical_travel_time", 0.0))

        base_eta = estimate_eta_minutes(distance_km, road_speed)
        corrected = corrected_eta_minutes(base_eta, traffic_level, hour)

        x: List[float] = [distance_km, traffic_level, float(hour), road_speed]
        reg = self.linear.predict_one(x) if self.linear.weights else corrected
        if hist_travel_time > 0:
            reg = 0.7 * reg + 0.3 * hist_travel_time

        return round(max(1.0, 0.5 * corrected + 0.5 * reg), 2)

    def save(self) -> str:
        payload = {
            "linear": self.linear.to_dict(),
            "default_speed_kmh": self.default_speed_kmh,
        }
        return save_json_weights("eta_weights.json", payload)
