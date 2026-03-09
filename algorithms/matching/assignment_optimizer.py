"""Assignment optimizer with fairness balancing."""

from __future__ import annotations

from typing import Dict, List

from algorithms.matching.distance_algorithm import (
    build_grid_index,
    haversine_km,
    query_nearest_drivers,
)
from algorithms.matching.driver_scoring import MatchingWeights, score_driver


def optimize_assignment(passenger: Dict, drivers: List[Dict], fairness_state: Dict[int, int]) -> Dict:
    if not drivers:
        return {}

    index = build_grid_index(drivers)
    nearby = query_nearest_drivers(
        index,
        passenger_lat=float(passenger["lat"]),
        passenger_lng=float(passenger["lng"]),
        max_cells=2,
        limit=35,
    )
    if not nearby:
        nearby = drivers

    weights = MatchingWeights()
    ranked = []
    for d in nearby:
        dist = haversine_km(float(passenger["lat"]), float(passenger["lng"]), float(d["lat"]), float(d["lng"]))
        eta_pickup = dist / max(8.0, float(d.get("speed_kmh", 26.0))) * 60.0
        features = {
            "distance_km": dist,
            "driver_rating": d.get("rating", 4.0),
            "availability": d.get("available", True),
            "eta_pickup_minutes": eta_pickup,
            "acceptance_probability": d.get("acceptance_probability", 0.85),
        }
        raw = score_driver(features, weights)

        # Fairness: penalize repeatedly selected drivers.
        historical_assignments = fairness_state.get(int(d["driver_id"]), 0)
        fairness_factor = 1.0 / (1.0 + 0.08 * historical_assignments)
        ranked.append({
            "driver": d,
            "score": raw * fairness_factor,
            "eta_pickup_minutes": round(eta_pickup, 2),
            "distance_km": round(dist, 3),
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    best = ranked[0]
    return {
        "driver_id": int(best["driver"]["driver_id"]),
        "score": round(float(best["score"]), 6),
        "distance_km": best["distance_km"],
        "eta_pickup_minutes": best["eta_pickup_minutes"],
    }
