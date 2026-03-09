"""Route-distance ETA estimation utilities."""

from __future__ import annotations

from algorithms.matching.distance_algorithm import haversine_km


def estimate_route_distance_km(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> float:
    return haversine_km(origin_lat, origin_lng, destination_lat, destination_lng)


def estimate_eta_minutes(distance_km: float, road_speed_kmh: float) -> float:
    speed = max(8.0, road_speed_kmh)
    return (distance_km / speed) * 60.0
