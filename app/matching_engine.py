"""matching_engine.py — Advanced multi-criteria driver-passenger matching.

Weighted scoring formula:
    score = 0.35 * proximity_score
          + 0.25 * rating_score
          + 0.15 * demand_zone_score
          + 0.15 * idle_time_score
          + 0.10 * acceptance_rate_score

Proximity is computed via the haversine formula.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from app.utils import logger


# ---------------------------------------------------------------------------
# Score helpers — all return 0.0–1.0
# ---------------------------------------------------------------------------
def _proximity_score(driver_lat: float, driver_lng: float,
                     pickup_lat: float, pickup_lng: float,
                     max_km: float = 15.0) -> float:
    dist = _haversine(driver_lat, driver_lng, pickup_lat, pickup_lng)
    return max(0.0, 1.0 - dist / max_km)


def _rating_score(rating: float) -> float:
    return max(0.0, min(1.0, (rating - 1.0) / 4.0))  # 1–5 → 0–1


def _demand_zone_score(demand_score: float) -> float:
    return float(min(1.0, max(0.0, demand_score)))


def _idle_time_score(idle_minutes: float, max_minutes: float = 120.0) -> float:
    """Prioritise drivers who have been idle longer (fairer distribution)."""
    return min(1.0, idle_minutes / max_minutes)


def _acceptance_rate_score(rate: float) -> float:
    return min(1.0, max(0.0, rate))


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin(math.radians(lat2 - lat1) / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(max(a, 0.0)))


# ---------------------------------------------------------------------------
# ETA helper (minutes) — straight-line with speed heuristic
# ---------------------------------------------------------------------------
def _estimate_arrival_minutes(dist_km: float, traffic_level: int) -> float:
    base_speed = {1: 45, 2: 40, 3: 30, 4: 20, 5: 12}.get(traffic_level, 30)
    return round((dist_km / base_speed) * 60, 1)


# ---------------------------------------------------------------------------
# MatchingEngine
# ---------------------------------------------------------------------------
class MatchingEngine:
    """Scores a list of candidate drivers against a passenger request."""

    WEIGHTS = {
        "proximity": 0.35,
        "rating": 0.25,
        "demand_zone": 0.15,
        "idle_time": 0.15,
        "acceptance_rate": 0.10,
    }

    def rank(
        self,
        pickup_lat: float,
        pickup_lng: float,
        candidates: List[Dict[str, Any]],
        traffic_level: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Score and sort candidates.

        Each candidate dict must contain:
          driver_id, name, lat, lng, rating, idle_minutes,
          acceptance_rate, demand_score  (all optional — defaults applied)
        """
        scored = []
        for c in candidates:
            driver_lat = float(c.get("lat") or c.get("latitude") or 0)
            driver_lng = float(c.get("lng") or c.get("longitude") or 0)
            rating = float(c.get("rating") or 3.0)
            idle_min = float(c.get("idle_minutes") or 10)
            accept_rate = float(c.get("acceptance_rate") or 0.85)
            demand = float(c.get("demand_score") or 0.5)

            p = _proximity_score(driver_lat, driver_lng, pickup_lat, pickup_lng)
            r = _rating_score(rating)
            d = _demand_zone_score(demand)
            i = _idle_time_score(idle_min)
            a = _acceptance_rate_score(accept_rate)

            w = self.WEIGHTS
            total = (
                w["proximity"] * p
                + w["rating"] * r
                + w["demand_zone"] * d
                + w["idle_time"] * i
                + w["acceptance_rate"] * a
            )

            dist_km = _haversine(driver_lat, driver_lng, pickup_lat, pickup_lng)
            eta = _estimate_arrival_minutes(dist_km, traffic_level)

            scored.append({
                "driver_id": c.get("id") or c.get("driver_id"),
                "driver_name": c.get("name") or c.get("driver_name"),
                "rating": round(rating, 2),
                "total_rides": c.get("total_rides"),
                "distance_to_passenger_km": round(dist_km, 3),
                "estimated_arrival_minutes": eta,
                "matching_score": round(total, 4),
                "score_breakdown": {
                    "proximity": round(p, 4),
                    "rating": round(r, 4),
                    "demand_zone": round(d, 4),
                    "idle_time": round(i, 4),
                    "acceptance_rate": round(a, 4),
                },
            })

        scored.sort(key=lambda x: x["matching_score"], reverse=True)
        logger.debug("Matching engine ranked %d candidates", len(scored))
        return scored


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_engine: Optional[MatchingEngine] = None


def get_engine() -> MatchingEngine:
    global _engine
    if _engine is None:
        _engine = MatchingEngine()
    return _engine
