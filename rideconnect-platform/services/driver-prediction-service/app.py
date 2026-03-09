"""Driver movement prediction service (Markov + probabilistic modeling)."""

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

from prediction.driver_movement_model import DriverMovementModel

app = FastAPI(title="RideConnect Driver Prediction Service", version="1.0.0")
model = DriverMovementModel()


class DriverMovementRequest(BaseModel):
    city_id: str
    driver_id: str
    driver_current_location: Dict[str, float]
    recent_trip_history: List[Dict[str, float]] = Field(default_factory=list)
    demand_heatmap: Dict[str, float] = Field(default_factory=dict)
    time_of_day: int = Field(12, ge=0, le=23)
    traffic_conditions: float = Field(0.4, ge=0.0, le=1.0)


@app.post("/driver-prediction/next-location")
def predict_next(payload: DriverMovementRequest) -> Dict:
    return model.predict_next_location(
        city_id=payload.city_id,
        driver_id=payload.driver_id,
        driver_current_location=payload.driver_current_location,
        recent_trip_history=payload.recent_trip_history,
        demand_heatmap=payload.demand_heatmap,
        time_of_day=payload.time_of_day,
        traffic_conditions=payload.traffic_conditions,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8105")))
