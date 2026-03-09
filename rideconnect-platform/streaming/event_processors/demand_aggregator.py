"""Aggregates ride request events into zone-level demand counts."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict, Iterable


class DemandAggregator:
    def __init__(self) -> None:
        self.zone_counts: DefaultDict[str, int] = defaultdict(int)

    def process(self, events: Iterable[Dict]) -> Dict[str, int]:
        for e in events:
            if e.get("event_type") != "ride_requested":
                continue
            city = e.get("city_id", "kigali")
            zone = e.get("zone_id", "core")
            self.zone_counts[f"{city}:{zone}"] += 1
        return dict(self.zone_counts)
