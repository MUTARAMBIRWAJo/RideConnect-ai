"""Route for dynamic ride price prediction."""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import require_api_key
from models.pricing_model import PricingModel

router = APIRouter()
_model = PricingModel()


class PredictPriceRequest(BaseModel):
    distance: float = Field(..., gt=0)
    duration: float = Field(..., gt=0)
    demand_level: float = Field(0.5, ge=0.0, le=1.0)
    traffic_level: float = Field(0.5, ge=0.0, le=1.0)
    time_of_day: int = Field(12, ge=0, le=23)
    city_zone: str = "A"
    corridor: str | None = None
    route_code: str | None = None
    origin_stop: str | None = None
    destination_stop: str | None = None


@router.post("/predict-price")
def predict_price(payload: PredictPriceRequest, _: None = Depends(require_api_key)) -> Dict:
    features = payload.model_dump()
    features["corridor"] = payload.corridor or payload.city_zone
    price = _model.predict(features)
    return {
        "status": "ok",
        "predicted_price": price,
        "currency": "RWF",
        "corridor": payload.corridor or payload.city_zone,
        "route_code": payload.route_code,
    }
