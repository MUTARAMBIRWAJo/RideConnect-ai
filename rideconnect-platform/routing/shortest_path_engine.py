"""Shortest path algorithms: Dijkstra and A* for routing engine."""

from __future__ import annotations

import heapq
import math
from typing import Dict, List, Tuple

from routing.graph_builder import Node, RoadGraph


def haversine_km(a: Node, b: Node) -> float:
    r = 6371.0
    lat1, lng1 = a
    lat2, lng2 = b
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    aa = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2.0) ** 2
    )
    return 2.0 * r * math.asin(math.sqrt(max(aa, 0.0)))


def _reconstruct(prev: Dict[Node, Node], end: Node) -> List[Node]:
    out = [end]
    cur = end
    while cur in prev:
        cur = prev[cur]
        out.append(cur)
    out.reverse()
    return out


def dijkstra(graph: RoadGraph, origin: Node, destination: Node, traffic_factor: float = 1.0) -> List[Node]:
    pq: List[Tuple[float, Node]] = [(0.0, origin)]
    dist: Dict[Node, float] = {origin: 0.0}
    prev: Dict[Node, Node] = {}

    while pq:
        cost, node = heapq.heappop(pq)
        if node == destination:
            return _reconstruct(prev, destination)
        if cost > dist.get(node, float("inf")):
            continue
        for edge in graph.neighbors(node):
            travel = (edge.distance_km / max(8.0, edge.speed_kmh)) * 60.0 * traffic_factor
            nxt_cost = cost + travel
            if nxt_cost < dist.get(edge.to, float("inf")):
                dist[edge.to] = nxt_cost
                prev[edge.to] = node
                heapq.heappush(pq, (nxt_cost, edge.to))
    return [origin, destination]


def astar(graph: RoadGraph, origin: Node, destination: Node, traffic_factor: float = 1.0) -> List[Node]:
    open_set: List[Tuple[float, Node]] = [(0.0, origin)]
    g_score: Dict[Node, float] = {origin: 0.0}
    prev: Dict[Node, Node] = {}

    while open_set:
        _, node = heapq.heappop(open_set)
        if node == destination:
            return _reconstruct(prev, destination)

        for edge in graph.neighbors(node):
            travel = (edge.distance_km / max(8.0, edge.speed_kmh)) * 60.0 * traffic_factor
            tentative = g_score[node] + travel
            if tentative < g_score.get(edge.to, float("inf")):
                prev[edge.to] = node
                g_score[edge.to] = tentative
                heuristic = (haversine_km(edge.to, destination) / 30.0) * 60.0
                f_score = tentative + heuristic
                heapq.heappush(open_set, (f_score, edge.to))

    return [origin, destination]
