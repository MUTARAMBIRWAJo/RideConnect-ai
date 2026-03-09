"""Road graph builder for city-specific routing."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import DefaultDict, Dict, List, Tuple

Node = Tuple[float, float]


@dataclass
class Edge:
    to: Node
    distance_km: float
    speed_kmh: float


class RoadGraph:
    def __init__(self) -> None:
        self.adj: DefaultDict[Node, List[Edge]] = defaultdict(list)

    def add_edge(self, a: Node, b: Node, distance_km: float, speed_kmh: float) -> None:
        self.adj[a].append(Edge(to=b, distance_km=distance_km, speed_kmh=speed_kmh))

    def neighbors(self, node: Node) -> List[Edge]:
        return self.adj.get(node, [])


def build_city_graph(city_config: Dict) -> RoadGraph:
    graph = RoadGraph()
    roads = city_config.get("roads", [])
    for r in roads:
        a = (float(r["from_lat"]), float(r["from_lng"]))
        b = (float(r["to_lat"]), float(r["to_lng"]))
        distance_km = float(r["distance_km"])
        speed_kmh = float(r.get("speed_kmh", 30.0))
        graph.add_edge(a, b, distance_km, speed_kmh)
        if bool(r.get("bidirectional", True)):
            graph.add_edge(b, a, distance_km, speed_kmh)
    return graph
