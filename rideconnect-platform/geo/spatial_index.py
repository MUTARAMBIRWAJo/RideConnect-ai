"""Spatial indexing for large driver fleets using a fixed-size grid."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Tuple

GridCell = Tuple[int, int]


class SpatialIndex:
    def __init__(self, cell_size_deg: float = 0.01) -> None:
        self.cell_size_deg = cell_size_deg
        self._cells: DefaultDict[GridCell, List[dict]] = defaultdict(list)

    def _key(self, lat: float, lng: float) -> GridCell:
        return (int(lat / self.cell_size_deg), int(lng / self.cell_size_deg))

    def bulk_load(self, points: Iterable[dict]) -> None:
        self._cells.clear()
        for p in points:
            self.insert(p)

    def insert(self, point: dict) -> None:
        key = self._key(float(point["lat"]), float(point["lng"]))
        self._cells[key].append(point)

    def query(self, lat: float, lng: float, radius_cells: int = 1) -> List[dict]:
        origin = self._key(lat, lng)
        out: List[dict] = []
        for i in range(-radius_cells, radius_cells + 1):
            for j in range(-radius_cells, radius_cells + 1):
                out.extend(self._cells.get((origin[0] + i, origin[1] + j), []))
        return out

    def stats(self) -> Dict[str, int]:
        points = sum(len(v) for v in self._cells.values())
        return {"active_cells": len(self._cells), "indexed_points": points}
