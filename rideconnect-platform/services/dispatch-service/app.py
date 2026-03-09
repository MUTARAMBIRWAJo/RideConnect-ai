"""Dispatch service for high-concurrency driver assignment."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from geo.spatial_index import SpatialIndex
from streaming.kafka_producer import RideEventProducer

app = FastAPI(title="RideConnect Dispatch Service", version="1.0.0")
index = SpatialIndex(cell_size_deg=0.01)
producer = RideEventProducer()


class DriverInput(BaseModel):
    driver_id: str
    lat: float
    lng: float
    rating: float = 4.0
    available: bool = True


class DispatchRequest(BaseModel):
    city_id: str
    ride_id: str
    passenger_lat: float
    passenger_lng: float
    drivers: List[DriverInput] = Field(default_factory=list)


@app.post("/dispatch/assign")
def assign_driver(payload: DispatchRequest) -> Dict:
    available = [d.model_dump() for d in payload.drivers if d.available]
    if not available:
        return {"status": "no_driver", "ride_id": payload.ride_id}

    index.bulk_load(available)
    nearby = index.query(payload.passenger_lat, payload.passenger_lng, radius_cells=2)
    if not nearby:
        nearby = available

    def score(d: Dict) -> float:
        dist = abs(d["lat"] - payload.passenger_lat) + abs(d["lng"] - payload.passenger_lng)
        return 1.0 / (0.001 + dist) + 0.1 * float(d.get("rating", 4.0))

    selected = max(nearby, key=score)
    event = {
        "event_type": "ride_assigned",
        "city_id": payload.city_id,
        "ride_id": payload.ride_id,
        "driver_id": selected["driver_id"],
        "zone_id": "core",
    }
    producer.publish_event("ride_status", event)

    return {
        "status": "assigned",
        "ride_id": payload.ride_id,
        "driver_id": selected["driver_id"],
        "score": round(score(selected), 5),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8101")))
