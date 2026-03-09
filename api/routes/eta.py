"""Route for ETA prediction inference."""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import require_api_key
from models.eta_model import ETAModel

router = APIRouter()
_model = ETAModel()


class PredictETARequest(BaseModel):
    origin_lat: float
    origin_lng: float
    destination_lat: float
    destination_lng: float
    traffic_level: float = Field(0.5, ge=0.0, le=1.0)
    time_of_day: int = Field(12, ge=0, le=23)
    road_speed_kmh: float = Field(28.0, gt=0)
    historical_travel_time: float = Field(0.0, ge=0)


@router.post("/predict-eta")
def predict_eta(payload: PredictETARequest, _: None = Depends(require_api_key)) -> Dict:
    eta = _model.predict_eta(payload.model_dump())
    return {
        "status": "ok",
        "predicted_eta_minutes": eta,
    }
