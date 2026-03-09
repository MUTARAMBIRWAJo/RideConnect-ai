"""Updates surge multipliers from demand and supply event streams."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict, Iterable


class SurgePricingUpdater:
    def __init__(self) -> None:
        self.multiplier: DefaultDict[str, float] = defaultdict(lambda: 1.0)

    def process(self, events: Iterable[Dict]) -> Dict[str, float]:
        demand: DefaultDict[str, int] = defaultdict(int)
        supply: DefaultDict[str, int] = defaultdict(int)

        for e in events:
            city = e.get("city_id", "kigali")
            zone = e.get("zone_id", "core")
            key = f"{city}:{zone}"
            if e.get("event_type") == "ride_requested":
                demand[key] += 1
            elif e.get("event_type") == "driver_location_updates":
                supply[key] += 1

        for key in set(demand) | set(supply):
            ratio = demand[key] / max(1, supply[key])
            self.multiplier[key] = max(1.0, min(2.6, 1.0 + 0.45 * max(0.0, ratio - 1.0)))

        return dict(self.multiplier)
