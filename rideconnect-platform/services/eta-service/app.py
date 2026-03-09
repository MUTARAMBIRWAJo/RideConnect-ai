"""ETA service powered by graph-based route optimization."""

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

from geo.city_zones import load_city_config
from online_learning.model_updater import load_model_weights
from routing.route_optimizer import compute_shortest_route, estimate_travel_time

app = FastAPI(title="RideConnect ETA Service", version="1.0.0")


class ETARequest(BaseModel):
    city_id: str
    origin_lat: float
    origin_lng: float
    destination_lat: float
    destination_lng: float
    traffic_level: float = Field(0.5, ge=0.0, le=1.0)
    algorithm: str = Field("astar")


@app.post("/eta/predict")
def predict_eta(payload: ETARequest) -> Dict:
    cfg = load_city_config(payload.city_id)
    route = compute_shortest_route(
        city_config=cfg,
        origin=(payload.origin_lat, payload.origin_lng),
        destination=(payload.destination_lat, payload.destination_lng),
        algorithm=payload.algorithm,
        traffic_level=payload.traffic_level,
    )
    eta = estimate_travel_time(route)

    learned = load_model_weights().get("eta_bias_minutes", {})
    bias = float(learned.get(f"{payload.city_id}:core", 0.0))

    return {
        "city_id": payload.city_id,
        "algorithm": payload.algorithm,
        "predicted_eta_minutes": round(max(1.0, eta + bias), 2),
        "route": [{"lat": p[0], "lng": p[1]} for p in route],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8103")))
