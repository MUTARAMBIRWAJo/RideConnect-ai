"""Generates city-zone heatmap intensity from ride event counts."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict, Iterable


class HeatmapGenerator:
    def process(self, events: Iterable[Dict]) -> Dict[str, float]:
        counts: DefaultDict[str, int] = defaultdict(int)
        for e in events:
            city = e.get("city_id", "kigali")
            zone = e.get("zone_id", "core")
            counts[f"{city}:{zone}"] += 1

        max_count = max(counts.values()) if counts else 1
        return {k: round(v / max_count, 4) for k, v in counts.items()}
