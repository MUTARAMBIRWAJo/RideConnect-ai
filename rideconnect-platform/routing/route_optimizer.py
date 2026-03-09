"""Traffic-weighted route optimization for pickup and trip routing."""

from __future__ import annotations

from typing import Dict, List, Tuple

from routing.graph_builder import Node, build_city_graph
from routing.shortest_path_engine import astar, dijkstra, haversine_km


def _traffic_factor(level: float) -> float:
    return max(0.8, min(2.5, 1.0 + 0.6 * max(0.0, level)))


def compute_shortest_route(
    city_config: Dict,
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    algorithm: str = "astar",
    traffic_level: float = 0.4,
) -> List[Node]:
    graph = build_city_graph(city_config)
    factor = _traffic_factor(traffic_level)
    if algorithm == "dijkstra":
        return dijkstra(graph, origin, destination, traffic_factor=factor)
    return astar(graph, origin, destination, traffic_factor=factor)


def estimate_travel_time(route: List[Node], avg_speed_kmh: float = 28.0) -> float:
    if len(route) < 2:
        return 0.0
    total_km = 0.0
    for i in range(len(route) - 1):
        total_km += haversine_km(route[i], route[i + 1])
    return round((total_km / max(8.0, avg_speed_kmh)) * 60.0, 2)


def optimize_route_for_pickup(
    city_config: Dict,
    driver_location: Tuple[float, float],
    passenger_location: Tuple[float, float],
    traffic_level: float = 0.5,
) -> Dict:
    route = compute_shortest_route(
        city_config=city_config,
        origin=driver_location,
        destination=passenger_location,
        algorithm="astar",
        traffic_level=traffic_level,
    )
    return {
        "route": [{"lat": p[0], "lng": p[1]} for p in route],
        "estimated_pickup_eta_minutes": estimate_travel_time(route),
    }
