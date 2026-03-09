"""Dynamic surge pricing calculation."""

from __future__ import annotations


def surge_multiplier(demand_level: float, traffic_level: float, hour: int) -> float:
    base = 1.0 + 0.4 * max(0.0, demand_level - 0.5) + 0.2 * max(0.0, traffic_level - 0.5)
    if 7 <= hour <= 9 or 17 <= hour <= 20:
        base += 0.15
    return max(1.0, min(2.5, base))


def compute_dynamic_price(
    base_fare: float,
    distance_km: float,
    duration_min: float,
    demand_level: float,
    traffic_level: float,
    hour: int,
    distance_rate: float,
    time_rate: float,
) -> float:
    multiplier = surge_multiplier(demand_level, traffic_level, hour)
    price = (
        base_fare
        + distance_rate * distance_km
        + time_rate * duration_min
    ) * multiplier
    return round(max(price, 1.0), 2)
