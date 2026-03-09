"""Route for demand forecasting inference."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import require_api_key
from models.demand_model import DemandModel

router = APIRouter()
_model = DemandModel()


class ForecastDemandRequest(BaseModel):
    zone: str
    hour: int = Field(default_factory=lambda: datetime.utcnow().hour, ge=0, le=23)
    is_weekend: bool = False
    weather_factor: float = Field(1.0, ge=0.5, le=1.5)


@router.post("/forecast-demand")
def forecast_demand(payload: ForecastDemandRequest, _: None = Depends(require_api_key)) -> Dict:
    pred = _model.predict(
        zone=payload.zone,
        hour=payload.hour,
        is_weekend=payload.is_weekend,
        weather_factor=payload.weather_factor,
    )
    return {
        "status": "ok",
        **pred,
    }
