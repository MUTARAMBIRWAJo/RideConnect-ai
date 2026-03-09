"""Pricing service with online-adjusted city-aware fare prediction."""

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

from geo.city_zones import load_city_config, resolve_zone
from online_learning.model_updater import load_model_weights
from streaming.kafka_producer import RideEventProducer

app = FastAPI(title="RideConnect Pricing Service", version="1.0.0")
producer = RideEventProducer()


class PriceRequest(BaseModel):
    city_id: str
    pickup_lat: float
    pickup_lng: float
    distance_km: float = Field(..., gt=0)
    duration_min: float = Field(..., gt=0)
    demand_level: float = Field(0.5, ge=0.0, le=1.0)
    traffic_level: float = Field(0.5, ge=0.0, le=1.0)
    hour: int = Field(12, ge=0, le=23)


@app.post("/pricing/predict")
def predict_price(payload: PriceRequest) -> Dict:
    cfg = load_city_config(payload.city_id)
    zone = resolve_zone(payload.city_id, payload.pickup_lat, payload.pickup_lng)
    base = cfg["base_pricing"]

    peak = payload.hour in set(cfg["demand_patterns"]["morning_peak"] + cfg["demand_patterns"]["evening_peak"])
    peak_mult = cfg["traffic_profiles"]["peak_multiplier"] if peak else cfg["traffic_profiles"]["offpeak_multiplier"]

    learned = load_model_weights().get("price_multiplier", {})
    zone_key = f"{payload.city_id}:{zone}"
    learned_mult = float(learned.get(zone_key, 1.0))

    surge = 1.0 + 0.35 * max(0.0, payload.demand_level - 0.5) + 0.2 * max(0.0, payload.traffic_level - 0.5)

    fare = (
        float(base["base_fare"])
        + float(base["distance_rate"]) * payload.distance_km
        + float(base["time_rate"]) * payload.duration_min
    ) * peak_mult * learned_mult * surge

    producer.publish_event(
        "demand_metrics",
        {
            "event_type": "pricing_predicted",
            "city_id": payload.city_id,
            "zone_id": zone,
            "predicted_price": round(fare, 2),
        },
    )

    return {
        "city_id": payload.city_id,
        "zone_id": zone,
        "predicted_price": round(max(500.0, fare), 2),
        "currency": "RWF" if payload.city_id == "kigali" else ("KES" if payload.city_id == "nairobi" else "NGN"),
        "surge_multiplier": round(peak_mult * learned_mult * surge, 3),
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8102")))
