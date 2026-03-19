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
from api.services.colab_inference import get_colab_inference_service
from utils.rura_tariffs import corridor_reference_fare, lookup_rura_tariff
from utils.rura_zones import coords_to_zone

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


class DemandRequest(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    weekday: int = Field(..., ge=0, le=6)
    month: int = Field(..., ge=1, le=12)
    is_weekend: int = Field(..., ge=0, le=1)
    pickup_zone: str
    zone_hour_count: int = Field(5, ge=0)


class MatchRequest(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    weekday: int = Field(..., ge=0, le=6)
    is_weekend: int = Field(..., ge=0, le=1)
    is_rush_hour: int = Field(..., ge=0, le=1)
    pickup_zone: str
    dropoff_zone: str
    distance_km: float = Field(..., ge=0)
    driver_rating: float = Field(..., ge=0)
    driver_idle_time: float = Field(..., ge=0)
    driver_cancel_rate: float = Field(..., ge=0)
    driver_avg_rating: float = Field(..., ge=0)
    driver_total_rides: int = Field(..., ge=0)
    surge_multiplier: float = Field(..., ge=1.0)
    demand_level: str


class BehaviorRequest(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    weekday: int = Field(..., ge=0, le=6)
    is_rush_hour: int = Field(..., ge=0, le=1)
    driver_rating: float = Field(..., ge=0)
    driver_idle_time: float = Field(..., ge=0)
    driver_total_rides: int = Field(..., ge=0)
    driver_cancel_rate: float = Field(..., ge=0)
    distance_km: float = Field(..., ge=0)
    duration_min: float = Field(..., ge=0)
    fare_rwf: float = Field(..., ge=0)
    surge_multiplier: float = Field(..., ge=1.0)
    pickup_zone: str


class SurgeRequest(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    weekday: int = Field(..., ge=0, le=6)
    is_weekend: int = Field(..., ge=0, le=1)
    is_rush_hour: int = Field(..., ge=0, le=1)
    month: int = Field(..., ge=1, le=12)
    pickup_zone: str
    distance_km: float = Field(..., ge=0)
    zone_hour_count: int = Field(5, ge=0)
    demand_level: str
    driver_idle_time: float = Field(..., ge=0)
    wait_time_min: float = Field(..., ge=0)


class LegacyPriceRequest(BaseModel):
    distance_km: float = Field(..., gt=0, le=500)
    demand_level: int = Field(..., ge=1, le=5)
    traffic_level: int = Field(..., ge=1, le=5)
    ride_type: str = Field("standard")
    corridor: str | None = None
    route_code: str | None = None
    origin_stop: str | None = None
    destination_stop: str | None = None


class LegacyDriverRequest(BaseModel):
    pickup_lat: float = Field(..., ge=-90, le=90)
    pickup_lng: float = Field(..., ge=-180, le=180)
    ride_type: str = Field("standard")


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


def _colab_service():
    try:
        return get_colab_inference_service()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Colab model service unavailable: {exc}") from exc


def _coords_to_colab_zone(lat: float, lng: float) -> str:
    return coords_to_zone(lat, lng)


def _demand_int_to_label(v: int) -> str:
    if v <= 2:
        return "low"
    if v == 3:
        return "medium"
    return "high"


def _ride_type_base_fare(ride_type: str) -> float:
    mapping = {
        "standard": 900.0,
        "premium": 1800.0,
        "boda": 550.0,
        "shared": 700.0,
    }
    return mapping.get(str(ride_type).lower(), 900.0)


def _build_legacy_price_response(payload: LegacyPriceRequest) -> dict[str, Any]:
    tariff = lookup_rura_tariff(
        route_code=payload.route_code,
        origin_stop=payload.origin_stop,
        destination_stop=payload.destination_stop,
        corridor=payload.corridor,
    )
    if tariff is not None:
        return {
            "recommended_price": float(tariff["fare_rwf"]),
            "currency": "RWF",
            "model_used": True,
            "cached": False,
            "fare_source": "rura_official",
            "corridor": tariff.get("corridor"),
            "route_code": tariff.get("route_code"),
            "origin_stop": tariff.get("origin_stop"),
            "destination_stop": tariff.get("destination_stop"),
        }

    now = time.localtime()
    hour = int(getattr(now, "tm_hour", 12) or 12)
    weekday = int(getattr(now, "tm_wday", 0) or 0)
    month = int(getattr(now, "tm_mon", 1) or 1)
    is_weekend = 1 if weekday >= 5 else 0
    is_rush_hour = 1 if (7 <= hour <= 9 or 17 <= hour <= 19) else 0

    demand_label = _demand_int_to_label(int(payload.demand_level))
    zone_hour_count = max(1, int(round(2 + payload.demand_level * 1.5)))
    wait_time = max(1.0, float(payload.traffic_level) * 2.2)
    idle_time = max(1.0, 24.0 - float(payload.demand_level) * 3.2)

    colab_req = {
        "hour": hour,
        "weekday": weekday,
        "is_weekend": is_weekend,
        "is_rush_hour": is_rush_hour,
        "month": month,
        "pickup_zone": "CBD",
        "distance_km": float(payload.distance_km),
        "zone_hour_count": zone_hour_count,
        "demand_level": demand_label,
        "driver_idle_time": round(idle_time, 2),
        "wait_time_min": round(wait_time, 2),
    }

    svc = _colab_service()
    pred = svc.predict_surge(colab_req)
    multiplier = float(pred.get("surge_multiplier", 1.0))

    base_fare = _ride_type_base_fare(payload.ride_type)
    distance_component = float(payload.distance_km) * 520.0
    recommended_price = round(max(500.0, (base_fare + distance_component) * multiplier), 2)

    corridor_anchor = corridor_reference_fare(payload.corridor)
    if corridor_anchor is not None:
        recommended_price = round(0.7 * corridor_anchor + 0.3 * recommended_price, 2)

    return {
        "recommended_price": recommended_price,
        "currency": "RWF",
        "model_used": True,
        "cached": False,
        "fare_source": "corridor_blend" if corridor_anchor is not None else "model_blend",
        "translated_colab_request": colab_req,
        "colab_response": pred,
    }


def _build_legacy_driver_response(payload: LegacyDriverRequest) -> dict[str, Any]:
    started = time.perf_counter()
    model = _load_model(MODEL_DIR / "driver_matching.pkl")
    drivers = model.get("drivers", []) if isinstance(model, dict) else []

    if not drivers:
        return {
            "driver_id": None,
            "driver_name": None,
            "rating": None,
            "total_rides": None,
            "note": "No active drivers available.",
        }

    best = min(
        drivers,
        key=lambda d: _haversine_distance_km(payload.pickup_lat, payload.pickup_lng, float(d["lat"]), float(d["lng"])),
    )

    now = time.localtime()
    hour = int(getattr(now, "tm_hour", 12) or 12)
    weekday = int(getattr(now, "tm_wday", 0) or 0)
    is_weekend = 1 if weekday >= 5 else 0
    is_rush_hour = 1 if (7 <= hour <= 9 or 17 <= hour <= 19) else 0
    pickup_zone = _coords_to_colab_zone(payload.pickup_lat, payload.pickup_lng)

    colab_req = {
        "hour": hour,
        "weekday": weekday,
        "is_weekend": is_weekend,
        "is_rush_hour": is_rush_hour,
        "pickup_zone": pickup_zone,
        "dropoff_zone": pickup_zone,
        "distance_km": 3.5,
        "driver_rating": 4.2,
        "driver_idle_time": 10.0,
        "driver_cancel_rate": 0.1,
        "driver_avg_rating": 4.2,
        "driver_total_rides": 200,
        "surge_multiplier": 1.0,
        "demand_level": "medium",
    }

    completion_prob = None
    try:
        completion_prob = _colab_service().predict_match(colab_req)
    except Exception:
        completion_prob = None

    latency_ms = int((time.perf_counter() - started) * 1000)
    note = "Selected nearest indexed driver (legacy compatibility)."
    if completion_prob is not None:
        note += f" Completion probability={completion_prob.get('completion_probability', 'n/a')}"

    return {
        "driver_id": int(best.get("driver_id", 0)) if best.get("driver_id") is not None else None,
        "driver_name": None,
        "rating": None,
        "total_rides": None,
        "note": note,
        "latency_ms": latency_ms,
        "translated_colab_request": colab_req,
        "colab_response": completion_prob,
    }


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


@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "running",
        "models": ["demand_lstm", "matching_rf", "behavior_gb", "surge_xgb"],
    }


@router.get("/models/info")
def models_info() -> dict[str, Any]:
    svc = _colab_service()
    try:
        return svc.model_info()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/predict/demand")
def predict_demand(payload: DemandRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    svc = _colab_service()
    try:
        return svc.predict_demand(payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/predict/match")
def predict_match(payload: MatchRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    svc = _colab_service()
    try:
        return svc.predict_match(payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/predict/behavior")
def predict_behavior(payload: BehaviorRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    svc = _colab_service()
    try:
        return svc.predict_behavior(payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/predict/surge")
def predict_surge(payload: SurgeRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    svc = _colab_service()
    try:
        return svc.predict_surge(payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/compat/predict-demand")
def compat_predict_demand(payload: DemandPredictRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    now = time.localtime()
    hour = int(payload.time_of_day)
    weekday = int(payload.day_of_week)
    month = int(getattr(now, "tm_mon", 1) or 1)
    zone = _coords_to_colab_zone(payload.lat, payload.lng)
    is_weekend = 1 if weekday >= 5 else 0
    zone_hour_count = max(1, int(round(payload.traffic_level * 4 + payload.weather * 3)))

    svc = _colab_service()
    colab_req = {
        "hour": hour,
        "weekday": weekday,
        "month": month,
        "is_weekend": is_weekend,
        "pickup_zone": zone,
        "zone_hour_count": zone_hour_count,
    }
    try:
        pred = svc.predict_demand(colab_req)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    label = str(pred.get("predicted_demand", "medium")).lower()
    demand_score = {"low": 2.5, "medium": 5.5, "high": 8.5}.get(label, 5.0)
    return {
        "status": "ok",
        "zone": zone,
        "predicted_demand_density": round(demand_score, 3),
        "hotspot_level": "high" if demand_score >= 8 else "medium" if demand_score >= 4 else "low",
        "translated_colab_request": colab_req,
        "colab_response": pred,
    }


@router.post("/compat/predict-price")
def compat_predict_price(payload: LegacyPriceRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    return _build_legacy_price_response(payload)


@router.post("/compat/predict-driver")
def compat_predict_driver(payload: LegacyDriverRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    return _build_legacy_driver_response(payload)


@router.post("/predict-price")
def legacy_predict_price_alias(payload: LegacyPriceRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    """Zero-change alias for old Laravel controller payload."""
    return _build_legacy_price_response(payload)


@router.post("/predict-driver")
def legacy_predict_driver_alias(payload: LegacyDriverRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    """Zero-change alias for old Laravel controller payload."""
    return _build_legacy_driver_response(payload)
