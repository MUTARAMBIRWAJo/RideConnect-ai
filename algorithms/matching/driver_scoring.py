"""Custom driver scoring model for assignment ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class MatchingWeights:
    distance_weight: float = 0.35
    rating_weight: float = 0.25
    availability_weight: float = 0.20
    pickup_time_weight: float = 0.20


def _normalize_distance(distance_km: float, max_distance_km: float = 12.0) -> float:
    return max(0.0, 1.0 - min(distance_km, max_distance_km) / max_distance_km)


def _normalize_pickup_time(eta_minutes: float, max_eta_minutes: float = 25.0) -> float:
    return max(0.0, 1.0 - min(eta_minutes, max_eta_minutes) / max_eta_minutes)


def score_driver(features: Dict, weights: MatchingWeights) -> float:
    distance_score = _normalize_distance(float(features["distance_km"]))
    rating_score = max(0.0, min(1.0, (float(features["driver_rating"]) - 1.0) / 4.0))
    availability = 1.0 if bool(features.get("availability", True)) else 0.0
    pickup_time_score = _normalize_pickup_time(float(features["eta_pickup_minutes"]))
    acceptance_prob = max(0.0, min(1.0, float(features.get("acceptance_probability", 0.8))))

    # Product scoring per requested optimization formulation.
    return (
        (weights.distance_weight * distance_score)
        * (weights.rating_weight * rating_score)
        * (weights.availability_weight * availability)
        * (weights.pickup_time_weight * pickup_time_score)
        * acceptance_prob
    )
