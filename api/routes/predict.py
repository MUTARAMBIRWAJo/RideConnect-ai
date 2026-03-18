"""Production prediction endpoints backed by trained RideConnect model artifacts."""

from __future__ import annotations

import math
import pickle
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import require_api_key

router = APIRouter()
MODEL_DIR = Path("models")


class MatchDriverRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class ETAPredictRequest(BaseModel):
    origin_lat: float = Field(..., ge=-90, le=90)
    origin_lng: float = Field(..., ge=-180, le=180)
    destination_lat: float = Field(..., ge=-90, le=90)
    destination_lng: float = Field(..., ge=-180, le=180)
    traffic_level: float = Field(0.35, ge=0.0, le=1.0)
    time_of_day: int = Field(12, ge=0, le=23)
    day_of_week: int = Field(0, ge=0, le=6)
    demand_density: float = Field(1.0, ge=0.0)
    driver_density: float = Field(1.0, ge=0.0)


class DemandPredictRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    time_of_day: int = Field(12, ge=0, le=23)
    day_of_week: int = Field(0, ge=0, le=6)
    traffic_level: float = Field(0.35, ge=0.0, le=1.0)
    weather: float = Field(1.0, ge=0.5, le=1.5)


class SurgePredictRequest(BaseModel):
    distance: float = Field(..., ge=0.0)
    estimated_time: float = Field(..., ge=0.0)
    demand_density: float = Field(..., ge=0.0)
    driver_density: float = Field(..., ge=0.0)
    traffic_level: float = Field(0.35, ge=0.0, le=1.0)
    time_of_day: int = Field(12, ge=0, le=23)
    day_of_week: int = Field(0, ge=0, le=6)


def _load_model(path: Path) -> Any:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"Model not trained yet: {path.name}")
    with path.open("rb") as f:
        return pickle.load(f)


def _haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(max(a, 0.0)))


@router.post("/predict/match-driver")
def match_driver(payload: MatchDriverRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    started = time.perf_counter()
    model = _load_model(MODEL_DIR / "driver_matching.pkl")

    drivers = model.get("drivers", []) if isinstance(model, dict) else []
    if not drivers:
        raise HTTPException(status_code=503, detail="Driver matching model has no driver index")

    best = min(drivers, key=lambda d: _haversine_distance_km(payload.lat, payload.lng, float(d["lat"]), float(d["lng"])))
    latency_ms = int((time.perf_counter() - started) * 1000)

    return {
        "status": "ok",
        "latency_ms": latency_ms,
        "result": {
            "driver_id": int(best["driver_id"]),
            "driver_lat": float(best["lat"]),
            "driver_lng": float(best["lng"]),
        },
    }


@router.post("/predict/eta")
def predict_eta(payload: ETAPredictRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    started = time.perf_counter()
    model = _load_model(MODEL_DIR / "eta_prediction.pkl")

    base_speed = float(model.get("base_speed_kmh", 28.0)) if isinstance(model, dict) else 28.0
    distance = _haversine_distance_km(payload.origin_lat, payload.origin_lng, payload.destination_lat, payload.destination_lng)

    adjusted_speed = max(8.0, base_speed * (1.05 - 0.55 * payload.traffic_level))
    predicted_minutes = max(1.0, (distance / adjusted_speed) * 60.0)

    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "status": "ok",
        "latency_ms": latency_ms,
        "predicted_eta_minutes": round(predicted_minutes, 2),
        "distance_km": round(distance, 3),
    }


@router.post("/predict/demand-hotspots")
def predict_demand_hotspots(payload: DemandPredictRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    started = time.perf_counter()
    model = _load_model(MODEL_DIR / "demand_prediction.pkl")

    zone = f"{round(payload.lat, 2)}:{round(payload.lng, 2)}"
    key = f"{zone}|{payload.time_of_day}|{payload.day_of_week}"

    profile = model.get("profile", {}) if isinstance(model, dict) else {}
    default = float(model.get("default", 1.0)) if isinstance(model, dict) else 1.0
    demand_score = float(profile.get(key, default)) * payload.weather

    hotspot_level = "high" if demand_score >= 8 else "medium" if demand_score >= 4 else "low"
    latency_ms = int((time.perf_counter() - started) * 1000)

    return {
        "status": "ok",
        "latency_ms": latency_ms,
        "zone": zone,
        "predicted_demand_density": round(max(0.0, demand_score), 3),
        "hotspot_level": hotspot_level,
    }


@router.post("/predict/surge-pricing")
def predict_surge_pricing(payload: SurgePredictRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    started = time.perf_counter()
    model = _load_model(MODEL_DIR / "surge_model.pkl")

    ratio_weight = float(model.get("ratio_weight", 0.35)) if isinstance(model, dict) else 0.35
    traffic_weight = float(model.get("traffic_weight", 0.15)) if isinstance(model, dict) else 0.15

    ratio = payload.demand_density / max(payload.driver_density, 0.1)
    multiplier = 1.0 + max(0.0, ratio - 1.0) * ratio_weight + payload.traffic_level * traffic_weight
    multiplier = max(1.0, min(3.0, multiplier))

    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "status": "ok",
        "latency_ms": latency_ms,
        "surge_multiplier": round(multiplier, 3),
        "demand_supply_ratio": round(ratio, 3),
    }
