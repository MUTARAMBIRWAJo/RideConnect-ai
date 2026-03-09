"""Route for driver-passenger matching inference."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import require_api_key
from models.matching_model import MatchingModel

router = APIRouter()
_model = MatchingModel()


class DriverInput(BaseModel):
    driver_id: int
    lat: float
    lng: float
    rating: float = 4.0
    available: bool = True
    speed_kmh: float = 26.0
    acceptance_probability: float = 0.85


class MatchDriverRequest(BaseModel):
    passenger_lat: float = Field(..., alias="lat")
    passenger_lng: float = Field(..., alias="lng")
    drivers: List[DriverInput]


@router.post("/match-driver")
def match_driver(payload: MatchDriverRequest, _: None = Depends(require_api_key)) -> Dict:
    passenger = {"lat": payload.passenger_lat, "lng": payload.passenger_lng}
    drivers = [d.model_dump() for d in payload.drivers]
    best = _model.predict_best_driver(passenger, drivers)
    return {
        "status": "ok",
        "result": best,
    }
