"""Traffic-aware route monitoring service."""

from __future__ import annotations

from typing import Dict

from app.model import haversine_km
from app.models.traffic_model import get_traffic_model
from app.route_optimizer import get_optimizer


class RouteMonitor:
    def __init__(self) -> None:
        self._traffic_model = get_traffic_model()
        self._route_optimizer = get_optimizer()

    def monitor(
        self,
        driver_lat: float,
        driver_lng: float,
        destination_lat: float,
        destination_lng: float,
    ) -> Dict:
        direct_km = haversine_km(driver_lat, driver_lng, destination_lat, destination_lng)
        traffic = self._traffic_model.estimate(distance_km=direct_km)

        # Build an alternative using dijkstra heuristic for comparison.
        alt = self._route_optimizer.optimize(
            pickup_lat=driver_lat,
            pickup_lng=driver_lng,
            dropoff_lat=destination_lat,
            dropoff_lng=destination_lng,
            traffic_level=4 if traffic["delay_minutes"] >= 5 else 3,
            algorithm="dijkstra",
        )

        delay = int(round(traffic["delay_minutes"]))
        status = "traffic_delay" if delay >= 3 else "normal"
        return {
            "status": status,
            "delay_minutes": delay,
            "recommended_route": alt["optimized_route"],
            "meta": {
                "baseline_minutes": traffic["baseline_minutes"],
                "traffic_minutes": traffic["traffic_minutes"],
                "congestion_factor": traffic["congestion_factor"],
            },
        }


_monitor = RouteMonitor()


def get_route_monitor() -> RouteMonitor:
    return _monitor
