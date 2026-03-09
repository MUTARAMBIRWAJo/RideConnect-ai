"""Online demand forecasting using EMA per city-zone."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict


class RideDemandModel:
    def __init__(self, alpha: float = 0.35) -> None:
        self.alpha = alpha
        self.zone_ema: DefaultDict[str, float] = defaultdict(lambda: 8.0)

    def update(self, city_id: str, zone_id: str, observed_requests: float) -> None:
        key = f"{city_id}:{zone_id}"
        prev = self.zone_ema[key]
        self.zone_ema[key] = self.alpha * observed_requests + (1.0 - self.alpha) * prev

    def predict(self, city_id: str, zone_id: str, hour: int, traffic_level: float) -> Dict:
        key = f"{city_id}:{zone_id}"
        base = self.zone_ema[key]
        hour_factor = 1.18 if (7 <= hour <= 9 or 17 <= hour <= 20) else 0.93
        traffic_factor = 1.0 + 0.2 * max(0.0, traffic_level)
        demand = base * hour_factor * traffic_factor
        return {
            "city_id": city_id,
            "zone_id": zone_id,
            "predicted_requests": round(demand, 2),
            "predicted_supply_needed": round(demand * 0.72, 2),
        }
