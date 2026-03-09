"""Distance and spatial indexing utilities for driver matching."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

GridKey = Tuple[int, int]


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2.0) ** 2
    )
    return 2.0 * r * math.asin(math.sqrt(max(a, 0.0)))


def build_grid_index(drivers: Iterable[Dict], cell_size_deg: float = 0.01) -> Dict[GridKey, List[Dict]]:
    index: Dict[GridKey, List[Dict]] = defaultdict(list)
    for d in drivers:
        lat = float(d["lat"])
        lng = float(d["lng"])
        key = (int(lat / cell_size_deg), int(lng / cell_size_deg))
        index[key].append(d)
    return index


def query_nearest_drivers(
    index: Dict[GridKey, List[Dict]],
    passenger_lat: float,
    passenger_lng: float,
    max_cells: int = 1,
    limit: int = 25,
    cell_size_deg: float = 0.01,
) -> List[Dict]:
    origin = (int(passenger_lat / cell_size_deg), int(passenger_lng / cell_size_deg))
    candidates: List[Dict] = []

    for i in range(-max_cells, max_cells + 1):
        for j in range(-max_cells, max_cells + 1):
            candidates.extend(index.get((origin[0] + i, origin[1] + j), []))

    candidates.sort(
        key=lambda d: haversine_km(passenger_lat, passenger_lng, float(d["lat"]), float(d["lng"]))
    )
    return candidates[:limit]
