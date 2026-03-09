"""Driver movement prediction using Markov transitions over city zones."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict, List

from geo.city_zones import resolve_zone


class DriverMovementModel:
    def __init__(self) -> None:
        self.transitions: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.driver_last_zone: Dict[str, str] = {}

    def observe_location(self, city_id: str, driver_id: str, lat: float, lng: float) -> None:
        zone = resolve_zone(city_id, lat, lng)
        prev = self.driver_last_zone.get(driver_id)
        if prev is not None:
            self.transitions[prev][zone] += 1
        self.driver_last_zone[driver_id] = zone

    def fit_from_trip_history(self, city_id: str, driver_id: str, locations: List[Dict]) -> None:
        for loc in locations:
            self.observe_location(city_id, driver_id, float(loc["lat"]), float(loc["lng"]))

    def predict_next_location(
        self,
        city_id: str,
        driver_id: str,
        driver_current_location: Dict,
        recent_trip_history: List[Dict],
        demand_heatmap: Dict[str, float],
        time_of_day: int,
        traffic_conditions: float,
    ) -> Dict:
        if recent_trip_history:
            self.fit_from_trip_history(city_id, driver_id, recent_trip_history)

        current_zone = resolve_zone(
            city_id,
            float(driver_current_location["lat"]),
            float(driver_current_location["lng"]),
        )
        outgoing = self.transitions.get(current_zone, {})

        total = sum(outgoing.values())
        probs: Dict[str, float] = {}
        if total > 0:
            for z, count in outgoing.items():
                probs[z] = count / total
        else:
            # Cold-start fallback weighted by demand heatmap.
            total_demand = sum(max(0.0, v) for v in demand_heatmap.values()) or 1.0
            for z, demand in demand_heatmap.items():
                probs[z] = max(0.0, demand) / total_demand

        # Time and traffic correction for stability.
        traffic_penalty = max(0.75, 1.0 - 0.25 * max(0.0, traffic_conditions))
        peak_bonus = 1.12 if (7 <= time_of_day <= 9 or 17 <= time_of_day <= 20) else 0.95
        adjusted = {z: max(1e-6, p * traffic_penalty * peak_bonus) for z, p in probs.items()}

        norm = sum(adjusted.values()) or 1.0
        adjusted = {z: round(v / norm, 4) for z, v in adjusted.items()}

        predicted_zone = max(adjusted, key=adjusted.get) if adjusted else current_zone
        return {
            "predicted_next_location": {
                "zone_id": predicted_zone,
                "lat": float(driver_current_location["lat"]),
                "lng": float(driver_current_location["lng"]),
            },
            "probability_distribution_of_zones": adjusted,
        }
