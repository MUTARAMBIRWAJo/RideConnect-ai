"""Inference wrapper for custom price prediction model."""

from __future__ import annotations

from typing import Dict, List

from algorithms.pricing.regression_model import LinearRegressionGD
from algorithms.pricing.surge_pricing import compute_dynamic_price
from utils.storage import load_json_weights, save_json_weights


class PricingModel:
    def __init__(self) -> None:
        payload = load_json_weights(
            "pricing_weights.json",
            {
                "linear": {"weights": [0.0, 0.0, 0.0, 0.0, 0.0], "bias": 0.0},
                "base_fare": 2.0,
                "distance_rate": 0.6,
                "time_rate": 0.12,
            },
        )
        self.linear = LinearRegressionGD.from_dict(payload.get("linear", {}))
        self.base_fare = float(payload.get("base_fare", 2.0))
        self.distance_rate = float(payload.get("distance_rate", 0.6))
        self.time_rate = float(payload.get("time_rate", 0.12))

    def predict(self, features: Dict) -> float:
        x: List[float] = [
            float(features["distance"]),
            float(features["duration"]),
            float(features.get("demand_level", 0.5)),
            float(features.get("traffic_level", 0.5)),
            float(features.get("time_of_day", 12.0)),
        ]
        reg_price = self.linear.predict_one(x) if self.linear.weights else 0.0

        rule_price = compute_dynamic_price(
            base_fare=self.base_fare,
            distance_km=x[0],
            duration_min=x[1],
            demand_level=x[2],
            traffic_level=x[3],
            hour=int(x[4]),
            distance_rate=self.distance_rate,
            time_rate=self.time_rate,
        )

        if reg_price <= 0:
            return float(rule_price)
        return round(max(1.0, 0.55 * reg_price + 0.45 * rule_price), 2)

    def save(self) -> str:
        payload = {
            "linear": self.linear.to_dict(),
            "base_fare": self.base_fare,
            "distance_rate": self.distance_rate,
            "time_rate": self.time_rate,
        }
        return save_json_weights("pricing_weights.json", payload)
