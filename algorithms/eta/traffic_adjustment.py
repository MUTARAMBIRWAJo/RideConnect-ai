"""Traffic correction logic for ETA predictions."""

from __future__ import annotations


def traffic_correction_factor(traffic_level: float, hour: int) -> float:
    factor = 1.0 + 0.45 * max(0.0, traffic_level)
    if 7 <= hour <= 9 or 17 <= hour <= 20:
        factor += 0.2
    return max(0.8, min(2.5, factor))


def corrected_eta_minutes(base_eta_minutes: float, traffic_level: float, hour: int) -> float:
    return base_eta_minutes * traffic_correction_factor(traffic_level, hour)
