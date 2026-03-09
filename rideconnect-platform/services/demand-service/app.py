"""Demand service for zone-level forecasting and stream-driven updates."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from prediction.ride_demand_model import RideDemandModel
from streaming.kafka_producer import RideEventProducer

app = FastAPI(title="RideConnect Demand Service", version="1.0.0")
model = RideDemandModel(alpha=0.35)
producer = RideEventProducer()


class DemandForecastRequest(BaseModel):
    city_id: str
    zone_id: str
    hour: int = Field(12, ge=0, le=23)
    traffic_level: float = Field(0.5, ge=0.0, le=1.0)


class DemandUpdateRequest(BaseModel):
    city_id: str
    zone_id: str
    observed_requests: float = Field(..., ge=0.0)


@app.post("/demand/forecast")
def forecast(payload: DemandForecastRequest) -> Dict:
    result = model.predict(payload.city_id, payload.zone_id, payload.hour, payload.traffic_level)
    producer.publish_event(
        "demand_metrics",
        {
            "event_type": "demand_forecasted",
            "city_id": payload.city_id,
            "zone_id": payload.zone_id,
            **result,
        },
    )
    return result


@app.post("/demand/update")
def update(payload: DemandUpdateRequest) -> Dict:
    model.update(payload.city_id, payload.zone_id, payload.observed_requests)
    return {"status": "updated", "city_id": payload.city_id, "zone_id": payload.zone_id}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8104")))
