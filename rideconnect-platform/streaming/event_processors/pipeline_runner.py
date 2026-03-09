"""Continuous event processing pipeline for demand, tracking, surge, and heatmap."""

from __future__ import annotations

import os
import time
from typing import Dict, List

from online_learning.incremental_training import IncrementalTrainer
from online_learning.model_updater import update_model_weights
from prediction.ride_demand_model import RideDemandModel
from streaming.event_processors.demand_aggregator import DemandAggregator
from streaming.event_processors.driver_location_tracker import DriverLocationTracker
from streaming.event_processors.heatmap_generator import HeatmapGenerator
from streaming.event_processors.surge_pricing_updater import SurgePricingUpdater
from streaming.kafka_consumer import RideEventConsumer


def _flatten(events_by_topic: Dict[str, List[Dict]]) -> List[Dict]:
    out: List[Dict] = []
    for evs in events_by_topic.values():
        out.extend(evs)
    return out


def run_forever(poll_seconds: float = 0.5) -> None:
    consumer = RideEventConsumer()
    demand_agg = DemandAggregator()
    tracker = DriverLocationTracker()
    surge = SurgePricingUpdater()
    heatmap = HeatmapGenerator()

    demand_model = RideDemandModel(alpha=0.35)
    trainer = IncrementalTrainer(demand_model)

    topics = ["ride_requests", "driver_locations", "ride_status", "demand_metrics"]

    while True:
        by_topic = {t: consumer.consume_events(t, max_messages=500) for t in topics}
        events = _flatten(by_topic)
        if not events:
            time.sleep(poll_seconds)
            continue

        demand = demand_agg.process(events)
        latest = tracker.process(events)
        surge_map = surge.process(events)
        heat = heatmap.process(events)

        for key, count in demand.items():
            city, zone = key.split(":", 1)
            trainer.update_demand(city, zone, float(count))
            supply = sum(1 for d in latest.values() if d["city_id"] == city)
            trainer.update_pricing(city, zone, observed_demand=float(count), available_drivers=float(supply))

        for e in events:
            if e.get("event_type") == "ride_completed":
                city = e.get("city_id", "kigali")
                zone = e.get("zone_id", "core")
                pred = float(e.get("predicted_eta_minutes", 10.0))
                actual = float(e.get("actual_eta_minutes", pred))
                trainer.update_eta(city, zone, pred, actual)

        update_model_weights(trainer)
        print(
            {
                "events": len(events),
                "zones": len(demand),
                "tracked_drivers": len(latest),
                "surge_zones": len(surge_map),
                "heatmap_zones": len(heat),
            }
        )


if __name__ == "__main__":
    run_forever(poll_seconds=float(os.getenv("PIPELINE_POLL_SECONDS", "0.5")))
