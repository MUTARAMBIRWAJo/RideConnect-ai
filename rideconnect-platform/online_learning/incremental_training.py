"""Incremental model updates from streaming ride events."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict

from prediction.ride_demand_model import RideDemandModel


class IncrementalTrainer:
    def __init__(self, demand_model: RideDemandModel) -> None:
        self.demand_model = demand_model
        self.price_multiplier: DefaultDict[str, float] = defaultdict(lambda: 1.0)
        self.eta_bias_minutes: DefaultDict[str, float] = defaultdict(float)

    def _city_key(self, city_id: str, zone_id: str) -> str:
        return f"{city_id}:{zone_id}"

    def update_pricing(self, city_id: str, zone_id: str, observed_demand: float, available_drivers: float) -> None:
        key = self._city_key(city_id, zone_id)
        ratio = observed_demand / max(1.0, available_drivers)
        target = max(0.85, min(2.2, 1.0 + 0.35 * (ratio - 1.0)))
        self.price_multiplier[key] = 0.9 * self.price_multiplier[key] + 0.1 * target

    def update_eta(self, city_id: str, zone_id: str, predicted_eta: float, actual_eta: float) -> None:
        key = self._city_key(city_id, zone_id)
        err = actual_eta - predicted_eta
        self.eta_bias_minutes[key] = 0.92 * self.eta_bias_minutes[key] + 0.08 * err

    def update_demand(self, city_id: str, zone_id: str, observed_requests: float) -> None:
        self.demand_model.update(city_id, zone_id, observed_requests)

    def feature_extract(self, event: Dict) -> Dict:
        return {
            "city_id": event.get("city_id", "kigali"),
            "zone_id": event.get("zone_id", "core"),
            "event_type": event.get("event_type", "unknown"),
            "traffic_level": float(event.get("traffic_level", 0.4)),
        }
