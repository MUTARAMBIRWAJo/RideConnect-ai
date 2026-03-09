"""Tracks latest driver locations from real-time movement events."""

from __future__ import annotations

from typing import Dict, Iterable


class DriverLocationTracker:
    def __init__(self) -> None:
        self.latest: Dict[str, Dict] = {}

    def process(self, events: Iterable[Dict]) -> Dict[str, Dict]:
        for e in events:
            if e.get("event_type") != "driver_location_updates":
                continue
            did = str(e.get("driver_id"))
            self.latest[did] = {
                "city_id": e.get("city_id", "kigali"),
                "lat": float(e.get("lat", 0.0)),
                "lng": float(e.get("lng", 0.0)),
                "traffic_level": float(e.get("traffic_level", 0.4)),
                "timestamp": e.get("timestamp"),
            }
        return self.latest
