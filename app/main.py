"""main.py — RideConnect AI Service — FastAPI application (v2.0)

All endpoints listed below.  Existing endpoints unchanged.

Health:
  GET  /                    — liveness (no auth)
  GET  /health              — readiness: model + DB status

Predictions (existing):
  POST /predict-price       — dynamic pricing
  POST /predict-driver      — simple best-driver selection (legacy)

Advanced AI (new):
  POST /match-driver        — weighted multi-criteria driver matching
  POST /predict-demand      — LSTM/RF demand forecasting
  GET  /demand-hotspots     — K-Means demand zone clusters
  POST /optimize-route      — A* / Dijkstra route optimisation
  POST /estimate-arrival    — GradientBoosting ETA
  POST /analyze-driver      — driver behaviour classification
  POST /detect-fare-anomaly — IsolationForest + Z-score anomaly detection

Driver Tracking:
  POST /update-driver-location — persist GPS location
  GET  /nearby-drivers         — drivers within radius

Data (existing):
  GET  /rides               — paginated ride listing
  GET  /trips               — paginated trip listing

Analytics:
  GET  /analytics/demand          — demand summary
  GET  /analytics/rides           — ride statistics
  GET  /analytics/driver-performance — driver leaderboard
  GET  /analytics/system-health   — system metrics

Admin:
  POST /retrain             — trigger full model retraining pipeline

Authentication: X-API-Key header on all routes except GET /
Rate limiting: 60 req/min per IP (in-process token bucket)
"""

from __future__ import annotations

import datetime
import os
import random
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security, status
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field

from app import service
from app.utils import logger

PRICE_CACHE_TTL_SECONDS = int(os.getenv("PRICE_CACHE_TTL_SECONDS", "300"))
DEMAND_CACHE_TTL_SECONDS = int(os.getenv("DEMAND_CACHE_TTL_SECONDS", "120"))

# ---------------------------------------------------------------------------
# Lazy-loaded AI modules (imported inside handlers to avoid startup errors
# when optional dependencies are absent)
# ---------------------------------------------------------------------------
def _demand():
    from app.demand_prediction import get_predictor
    return get_predictor()

def _hotspot():
    from app.hotspot_detection import get_detector
    return get_detector()

def _matcher():
    from app.matching_engine import get_engine
    return get_engine()

def _router():
    from app.route_optimizer import get_optimizer
    return get_optimizer()

def _eta():
    from app.eta_predictor import get_eta_predictor
    return get_eta_predictor()

def _behavior():
    from app.behavior_analysis import get_analyzer
    return get_analyzer()

def _anomaly():
    from app.anomaly_detection import get_anomaly_detector
    return get_anomaly_detector()

def _tracker():
    from app.driver_tracking import get_tracker
    return get_tracker()


# ---------------------------------------------------------------------------
# API Key auth
# ---------------------------------------------------------------------------
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: Optional[str] = Security(_api_key_header)) -> str:
    expected = service.API_KEY
    if not expected:
        return ""
    if key != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid or missing API key.")
    return key


# ---------------------------------------------------------------------------
# Rate limiter — simple in-process token bucket (60 req/min per IP)
# ---------------------------------------------------------------------------
_rate_buckets: dict = defaultdict(lambda: {"tokens": 60, "last": time.time()})
_RATE_LIMIT = 60
_RATE_WINDOW = 60.0


def _check_rate(ip: str) -> None:
    b = _rate_buckets[ip]
    now = time.time()
    elapsed = now - b["last"]
    b["tokens"] = min(_RATE_LIMIT, b["tokens"] + elapsed * (_RATE_LIMIT / _RATE_WINDOW))
    b["last"] = now
    if b["tokens"] < 1:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Retry after 60s.")
    b["tokens"] -= 1


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await service.startup()
    # Pre-warm all AI modules so first requests are fast
    try:
        _demand(); _hotspot(); _matcher(); _router(); _eta(); _behavior(); _anomaly()
        logger.info("All AI modules pre-warmed.")
    except Exception as exc:
        logger.warning("AI module pre-warm partial failure: %s", exc)
    yield
    await service.shutdown()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="RideConnect AI Service",
    version="2.0.0",
    description="Full intelligent mobility AI/ML engine for RideConnect.",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware — timing + rate limiting
# ---------------------------------------------------------------------------
@app.middleware("http")
async def middleware(request: Request, call_next):
    start = time.time()
    ip = request.client.host if request.client else "unknown"
    if request.url.path != "/":
        try:
            _check_rate(ip)
        except HTTPException as e:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    response = await call_next(request)
    ms = round((time.time() - start) * 1000, 1)
    logger.info("%s %s → %d (%s ms)", request.method, request.url.path, response.status_code, ms)
    return response


# ===========================================================================
# SCHEMAS
# ===========================================================================
class PricePredictRequest(BaseModel):
    distance_km: float = Field(..., gt=0, le=500)
    demand_level: int = Field(..., ge=1, le=5)
    traffic_level: int = Field(..., ge=1, le=5)
    ride_type: str = Field("standard")

class PricePredictResponse(BaseModel):
    recommended_price: float
    currency: str = "KES"
    model_used: bool
    cached: bool = False

class DriverPredictRequest(BaseModel):
    pickup_lat: float
    pickup_lng: float
    ride_type: Optional[str] = "standard"

class DriverPredictResponse(BaseModel):
    driver_id: Optional[int]
    driver_name: Optional[str]
    rating: Optional[float]
    total_rides: Optional[int]
    note: str

class MatchDriverRequest(BaseModel):
    pickup_lat: float = Field(..., description="Passenger pickup latitude")
    pickup_lng: float = Field(..., description="Passenger pickup longitude")
    ride_type: Optional[str] = "standard"
    traffic_level: int = Field(3, ge=1, le=5)
    max_results: int = Field(5, ge=1, le=20)

class DemandRequest(BaseModel):
    latitude: float
    longitude: float
    hour: Optional[int] = None
    day_of_week: Optional[int] = None
    traffic_level: int = Field(3, ge=1, le=5)
    historical_count: int = Field(20, ge=0)
    weather: str = Field("clear")
    event_indicator: int = Field(0, ge=0, le=1)

class RouteRequest(BaseModel):
    pickup_lat: float
    pickup_lng: float
    dropoff_lat: float
    dropoff_lng: float
    traffic_level: int = Field(3, ge=1, le=5)
    checkpoints: Optional[List[Dict[str, float]]] = None
    algorithm: str = Field("astar", description="astar | dijkstra")

class ETARequest(BaseModel):
    distance_km: float = Field(..., gt=0)
    traffic_level: int = Field(3, ge=1, le=5)
    road_type: str = Field("main_road")
    weather: str = Field("clear")
    hour: Optional[int] = None
    day_of_week: Optional[int] = None
    historical_duration_avg: Optional[float] = None

class BehaviorRequest(BaseModel):
    driver_id: Optional[int] = None
    avg_trip_duration_min: float = Field(30.0, ge=1)
    avg_speed_kmh: float = Field(35.0, ge=1)
    cancellation_rate: float = Field(0.05, ge=0, le=1)
    avg_rating: float = Field(4.0, ge=1, le=5)
    route_deviation_pct: float = Field(5.0, ge=0)
    total_rides: int = Field(50, ge=0)

class AnomalyRequest(BaseModel):
    fare: float = Field(..., gt=0)
    distance_km: float = Field(..., gt=0)
    demand_level: int = Field(3, ge=1, le=5)
    trip_id: Optional[int] = None

class LocationUpdateRequest(BaseModel):
    driver_id: int
    latitude: float
    longitude: float
    heading: Optional[float] = None
    speed_kmh: Optional[float] = None

class RetrainRequest(BaseModel):
    models: Optional[List[str]] = None  # None = all


# ===========================================================================
# ROUTES — Health
# ===========================================================================
@app.get("/", tags=["Health"])
def root():
    return {"service": "RideConnect AI", "status": "running", "version": "2.0.0", "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health_check(_: str = Depends(require_api_key)):
    db_ok = False
    redis_ok = False
    try:
        await service.database.fetch_one("SELECT 1")
        db_ok = True
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)

    try:
        if service.redis_client is not None:
            redis_ok = bool(await service.redis_client.ping())
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)

    modules = {
        "price_model":    service.price_model.is_loaded,
        "demand_model":   _demand().is_loaded,
        "eta_model":      _eta().is_loaded,
        "behavior_model": _behavior().is_loaded,
        "anomaly_model":  _anomaly().is_loaded,
        "hotspot_model":  _hotspot().is_fitted,
    }
    all_ok = all(modules.values()) and db_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "database_connected": db_ok,
        "redis_connected": redis_ok,
        "models": modules,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }


# ===========================================================================
# ROUTES — Predictions (existing)
# ===========================================================================
@app.post("/predict-price", response_model=PricePredictResponse, tags=["Predictions"])
async def predict_price(body: PricePredictRequest, _: str = Depends(require_api_key)):
    cache_key = (
        "rideconnect:cache:price:"
        f"{body.distance_km}:{body.demand_level}:{body.traffic_level}:{body.ride_type}"
    )
    cached_payload = await service.cache_get_json(cache_key)
    if cached_payload:
        cached = dict(cached_payload)
        cached["cached"] = True
        return PricePredictResponse(**cached)

    price = service.price_model.predict(
        distance_km=body.distance_km, demand_level=body.demand_level,
        traffic_level=body.traffic_level, ride_type=body.ride_type,
    )
    payload = {"recommended_price": price, "currency": "KES",
               "model_used": service.price_model.is_loaded, "cached": False}
    await service.cache_set_json(cache_key, payload, ttl_seconds=PRICE_CACHE_TTL_SECONDS)

    try:
        await service.database.execute(
            "INSERT INTO ai_price_predictions "
            "(distance_km,demand_level,traffic_level,ride_type,predicted_price) "
            "VALUES (:dist,:demand,:traffic,:ride_type,:price)",
            {"dist": body.distance_km, "demand": body.demand_level,
             "traffic": body.traffic_level, "ride_type": body.ride_type, "price": price},
        )
    except Exception:
        pass
    return PricePredictResponse(**payload)


@app.post("/predict-driver", response_model=DriverPredictResponse, tags=["Predictions"])
async def predict_driver(body: DriverPredictRequest, _: str = Depends(require_api_key)):
    try:
        rows = await service.database.fetch_all(
            "SELECT d.id, u.name, d.rating, d.total_rides FROM drivers d "
            "JOIN users u ON u.id=d.user_id WHERE d.status='active' AND d.deleted_at IS NULL "
            "ORDER BY d.rating DESC LIMIT 20"
        )
        if rows:
            weights = [float(r["rating"] or 1.0) for r in rows]
            driver = random.choices(rows, weights=weights, k=1)[0]
            return DriverPredictResponse(
                driver_id=driver["id"], driver_name=driver["name"],
                rating=float(driver["rating"] or 0), total_rides=driver["total_rides"],
                note="Selected by weighted rating (legacy endpoint).",
            )
    except Exception as exc:
        logger.warning("predict-driver DB error: %s", exc)
    return DriverPredictResponse(driver_id=None, driver_name=None, rating=None,
                                  total_rides=None, note="No active drivers available.")


# ===========================================================================
# ROUTES — Advanced AI
# ===========================================================================
@app.post("/match-driver", tags=["Advanced AI"])
async def match_driver(body: MatchDriverRequest, _: str = Depends(require_api_key)):
    """Multi-criteria weighted driver matching."""
    try:
        rows = await service.database.fetch_all(
            """
            SELECT DISTINCT ON (dl.driver_id)
                   dl.driver_id AS id, u.name,
                   dl.latitude, dl.longitude,
                   d.rating, d.total_rides,
                   ds.idle_since
            FROM   driver_locations dl
            JOIN   drivers d  ON d.id = dl.driver_id
            JOIN   users   u  ON u.id = d.user_id
            LEFT JOIN driver_status ds ON ds.driver_id = dl.driver_id
            WHERE  dl.recorded_at >= NOW() - INTERVAL '15 minutes'
              AND  COALESCE(ds.status, 'online') IN ('online')
              AND  d.deleted_at IS NULL
            ORDER  BY dl.driver_id, dl.recorded_at DESC
            LIMIT  50
            """
        )
        candidates = []
        for r in rows:
            idle_min = 10.0
            if r["idle_since"]:
                idle_min = (datetime.datetime.utcnow() -
                            r["idle_since"].replace(tzinfo=None)).total_seconds() / 60
            candidates.append({
                "id": r["id"], "name": r["name"],
                "latitude": float(r["latitude"]), "longitude": float(r["longitude"]),
                "rating": float(r["rating"] or 3.0),
                "total_rides": r["total_rides"],
                "idle_minutes": idle_min,
                "acceptance_rate": 0.88,
                "demand_score": 0.5,
            })
    except Exception as exc:
        logger.warning("match-driver DB query error: %s", exc)
        candidates = []

    if not candidates:
        return {"matches": [], "note": "No online drivers with recent location data."}

    ranked = _matcher().rank(body.pickup_lat, body.pickup_lng, candidates, body.traffic_level)
    return {"matches": ranked[: body.max_results], "total_candidates": len(candidates)}


@app.post("/predict-demand", tags=["Advanced AI"])
async def predict_demand(body: DemandRequest, _: str = Depends(require_api_key)):
    """Returns demand forecast for a lat/lng coordinate."""
    now = datetime.datetime.now()
    hour = body.hour if body.hour is not None else now.hour
    dow = body.day_of_week if body.day_of_week is not None else now.weekday()

    cache_key = (
        "rideconnect:cache:demand:"
        f"{round(body.latitude, 2)}:{round(body.longitude, 2)}:{hour}:{dow}:"
        f"{body.traffic_level}:{body.weather}:{body.event_indicator}"
    )
    cached_payload = await service.cache_get_json(cache_key)
    if cached_payload:
        return cached_payload

    result = _demand().predict(
        hour=hour, day_of_week=dow,
        traffic_level=body.traffic_level,
        historical_count=body.historical_count,
        lat=body.latitude, lng=body.longitude,
        weather=body.weather,
        event_indicator=body.event_indicator,
    )

    # Nearest zone lookup
    zone_id = None
    zone_name = None
    try:
        rows = await service.database.fetch_all(
            "SELECT id, zone_name, center_lat::float AS lat, center_lng::float AS lng "
            "FROM demand_zones WHERE active=TRUE LIMIT 50"
        )
        if rows:
            from app.model import haversine_km
            nearest = min(rows, key=lambda r: haversine_km(
                body.latitude, body.longitude, r["lat"], r["lng"]))
            zone_id = nearest["id"]
            zone_name = nearest["zone_name"]
    except Exception:
        pass

    payload = {
        "zone_id": zone_id,
        "zone_name": zone_name,
        "latitude": body.latitude,
        "longitude": body.longitude,
        "hour": hour,
        "day_of_week": dow,
        **result,
    }
    await service.cache_set_json(cache_key, payload, ttl_seconds=DEMAND_CACHE_TTL_SECONDS)

    try:
        if zone_id:
            await service.database.execute(
                "INSERT INTO predicted_demand "
                "(zone_id,hour,day_of_week,demand_score,predicted_requests,confidence,weather_condition) "
                "VALUES (:zone_id,:hour,:dow,:score,:req,:conf,:weather)",
                {"zone_id": zone_id, "hour": hour, "dow": dow,
                 "score": result["demand_score"], "req": result["predicted_requests"],
                 "conf": result["confidence"], "weather": body.weather},
            )
    except Exception:
        pass
    return payload


@app.get("/demand-hotspots", tags=["Advanced AI"])
async def demand_hotspots(
    limit: int = Query(10, ge=1, le=50),
    _: str = Depends(require_api_key),
):
    """Returns top-N demand hotspot clusters."""
    hotspots = _hotspot().get_hotspots()[:limit]
    # Enrich with zone names if available
    try:
        zones = await service.database.fetch_all(
            "SELECT cluster_id, zone_name FROM demand_zones WHERE cluster_id IS NOT NULL"
        )
        zone_map = {r["cluster_id"]: r["zone_name"] for r in zones}
        for h in hotspots:
            h["zone_name"] = zone_map.get(h["cluster_id"])
    except Exception:
        pass
    return {"hotspots": hotspots, "total": len(hotspots)}


@app.post("/optimize-route", tags=["Advanced AI"])
async def optimize_route(body: RouteRequest, _: str = Depends(require_api_key)):
    """Optimise route between pickup and dropoff using A* or Dijkstra."""
    result = _router().optimize(
        pickup_lat=body.pickup_lat, pickup_lng=body.pickup_lng,
        dropoff_lat=body.dropoff_lat, dropoff_lng=body.dropoff_lng,
        traffic_level=body.traffic_level,
        checkpoints=body.checkpoints,
        algorithm=body.algorithm,
    )
    return result


@app.post("/estimate-arrival", tags=["Advanced AI"])
async def estimate_arrival(body: ETARequest, _: str = Depends(require_api_key)):
    """Predict travel time in minutes using GradientBoosting model."""
    eta_min = _eta().predict(
        distance_km=body.distance_km,
        traffic_level=body.traffic_level,
        hour=body.hour,
        day_of_week=body.day_of_week,
        road_type=body.road_type,
        weather=body.weather,
        historical_duration_avg=body.historical_duration_avg,
    )
    now = datetime.datetime.utcnow()
    arrival = now + datetime.timedelta(minutes=eta_min)
    return {
        "estimated_duration_minutes": eta_min,
        "estimated_arrival_utc": arrival.isoformat() + "Z",
        "distance_km": body.distance_km,
        "traffic_level": body.traffic_level,
        "model_used": _eta().is_loaded,
    }


@app.post("/analyze-driver", tags=["Advanced AI"])
async def analyze_driver(body: BehaviorRequest, _: str = Depends(require_api_key)):
    """Classify driver behaviour and optionally store in driver_behavior_logs."""
    result = _behavior().classify(
        avg_trip_duration_min=body.avg_trip_duration_min,
        avg_speed_kmh=body.avg_speed_kmh,
        cancellation_rate=body.cancellation_rate,
        avg_rating=body.avg_rating,
        route_deviation_pct=body.route_deviation_pct,
        total_rides=body.total_rides,
    )
    if body.driver_id:
        try:
            await service.database.execute(
                "INSERT INTO driver_behavior_logs "
                "(driver_id,behavior_class,confidence,avg_speed_kmh,cancellation_rate,avg_rating,raw_features) "
                "VALUES (:did,:cls,:conf,:spd,:cancel,:rating,:feat::jsonb)",
                {
                    "did": body.driver_id,
                    "cls": result["behavior_class"],
                    "conf": result["confidence"],
                    "spd": body.avg_speed_kmh,
                    "cancel": body.cancellation_rate,
                    "rating": body.avg_rating,
                    "feat": str({
                        "avg_trip_duration_min": body.avg_trip_duration_min,
                        "route_deviation_pct": body.route_deviation_pct,
                        "total_rides": body.total_rides,
                    }).replace("'", '"'),
                },
            )
        except Exception as exc:
            logger.warning("driver_behavior_logs insert failed: %s", exc)
    return {"driver_id": body.driver_id, **result}


@app.post("/detect-fare-anomaly", tags=["Advanced AI"])
async def detect_fare_anomaly(body: AnomalyRequest, _: str = Depends(require_api_key)):
    """Detect fare anomalies using IsolationForest and Z-score."""
    result = _anomaly().detect(
        fare=body.fare, distance_km=body.distance_km, demand_level=body.demand_level,
    )
    if result["anomaly_detected"]:
        logger.warning(
            "Fare anomaly detected | trip=%s  fare=%.2f  dist=%.2f  type=%s",
            body.trip_id, body.fare, body.distance_km, result["anomaly_type"],
        )
        try:
            await service.database.execute(
                "INSERT INTO fare_audit "
                "(trip_id,original_fare,anomaly_flag,anomaly_type,anomaly_score,z_score) "
                "VALUES (:tid,:fare,:flag,:atype,:score,:z)",
                {
                    "tid": body.trip_id, "fare": body.fare,
                    "flag": True, "atype": result["anomaly_type"],
                    "score": result["anomaly_score"], "z": result["z_score"],
                },
            )
        except Exception:
            pass
    return {"trip_id": body.trip_id, "fare": body.fare, **result}


# ===========================================================================
# ROUTES — Driver Tracking
# ===========================================================================
@app.post("/update-driver-location", tags=["Driver Tracking"])
async def update_driver_location(body: LocationUpdateRequest, _: str = Depends(require_api_key)):
    return await _tracker().update_location(
        service.database, body.driver_id,
        body.latitude, body.longitude,
        body.heading, body.speed_kmh,
    )


@app.get("/nearby-drivers", tags=["Driver Tracking"])
async def nearby_drivers(
    lat: float = Query(..., description="Pickup latitude"),
    lng: float = Query(..., description="Pickup longitude"),
    radius_km: float = Query(5.0, ge=0.5, le=50),
    limit: int = Query(10, ge=1, le=50),
    _: str = Depends(require_api_key),
):
    drivers = await _tracker().nearby_drivers(service.database, lat, lng, radius_km, limit)
    return {"drivers": drivers, "count": len(drivers), "radius_km": radius_km}


# ===========================================================================
# ROUTES — Data (existing)
# ===========================================================================
@app.get("/rides", tags=["Data"])
async def list_rides(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    _: str = Depends(require_api_key),
):
    try:
        where = "WHERE r.status = :status" if status_filter else ""
        params: dict = {"limit": limit, "offset": offset}
        if status_filter:
            params["status"] = status_filter
        rows = await service.database.fetch_all(
            f"SELECT r.id,r.origin_address,r.destination_address,r.price_per_seat,"
            f"r.currency,r.available_seats,r.ride_type,r.status,r.departure_time,r.created_at "
            f"FROM rides r {where} ORDER BY r.created_at DESC LIMIT :limit OFFSET :offset",
            params,
        )
        return {"data": [dict(r) for r in rows], "limit": limit, "offset": offset}
    except Exception as exc:
        logger.error("list_rides error: %s", exc)
        raise HTTPException(status_code=500, detail="Could not fetch rides.")


@app.get("/trips", tags=["Data"])
async def list_trips(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: str = Depends(require_api_key),
):
    try:
        rows = await service.database.fetch_all(
            "SELECT t.id,t.pickup_location,t.dropoff_location,t.fare,t.status,"
            "t.requested_at,t.completed_at FROM trips t "
            "ORDER BY t.created_at DESC LIMIT :limit OFFSET :offset",
            {"limit": limit, "offset": offset},
        )
        return {"data": [dict(r) for r in rows], "limit": limit, "offset": offset}
    except Exception as exc:
        logger.error("list_trips error: %s", exc)
        raise HTTPException(status_code=500, detail="Could not fetch trips.")


# ===========================================================================
# ROUTES — Analytics
# ===========================================================================
@app.get("/analytics/demand", tags=["Analytics"])
async def analytics_demand(_: str = Depends(require_api_key)):
    try:
        rows = await service.database.fetch_all(
            "SELECT zone_name, demand_score, ride_count, center_lat::float, center_lng::float "
            "FROM demand_zones WHERE active=TRUE ORDER BY demand_score DESC LIMIT 20"
        )
        return {"zones": [dict(r) for r in rows]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/analytics/rides", tags=["Analytics"])
async def analytics_rides(_: str = Depends(require_api_key)):
    try:
        summary = await service.database.fetch_one(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed, "
            "SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled, "
            "AVG(price_per_seat::float) AS avg_price "
            "FROM rides"
        )
        recent = await service.database.fetch_all(
            "SELECT ride_type, COUNT(*) AS count, AVG(price_per_seat::float) AS avg_price "
            "FROM rides GROUP BY ride_type ORDER BY count DESC"
        )
        return {"summary": dict(summary) if summary else {}, "by_type": [dict(r) for r in recent]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/analytics/driver-performance", tags=["Analytics"])
async def analytics_driver_performance(_: str = Depends(require_api_key)):
    try:
        rows = await service.database.fetch_all(
            "SELECT d.id, u.name, d.rating, d.total_rides, d.status, "
            "COALESCE(dbl.behavior_class,'unknown') AS behavior "
            "FROM drivers d "
            "JOIN users u ON u.id=d.user_id "
            "LEFT JOIN LATERAL ("
            "  SELECT behavior_class FROM driver_behavior_logs "
            "  WHERE driver_id=d.id ORDER BY analyzed_at DESC LIMIT 1"
            ") dbl ON TRUE "
            "WHERE d.deleted_at IS NULL "
            "ORDER BY d.rating DESC LIMIT 30"
        )
        return {"drivers": [dict(r) for r in rows], "total": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/analytics/system-health", tags=["Analytics"])
async def analytics_system_health(_: str = Depends(require_api_key)):
    db_ok = False
    try:
        await service.database.fetch_one("SELECT 1")
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "uptime_check": datetime.datetime.utcnow().isoformat() + "Z",
        "models": {
            "price": service.price_model.is_loaded,
            "demand": _demand().is_loaded,
            "eta": _eta().is_loaded,
            "behavior": _behavior().is_loaded,
            "anomaly": _anomaly().is_loaded,
            "hotspot": _hotspot().is_fitted,
        },
    }


# ===========================================================================
# ROUTES — Admin
# ===========================================================================
@app.post("/retrain", tags=["Admin"])
async def retrain(body: RetrainRequest, _: str = Depends(require_api_key)):
    """Trigger model retraining pipeline; queues job in Redis when enabled."""
    if service.REDIS_QUEUE_ENABLED and service.redis_client is not None:
        job_id = await service.enqueue_job(
            "retrain_models",
            payload={"models": body.models or []},
        )
        if job_id:
            return {
                "status": "queued",
                "job_id": job_id,
                "queue": service.REDIS_QUEUE_NAME,
                "note": "Track with GET /jobs/{job_id}.",
            }

    import asyncio
    from app.retraining import run_full_pipeline
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, run_full_pipeline)
    # Reload models after retraining
    service.price_model.load()
    _demand().load()
    _eta().load()
    _behavior().load()
    _anomaly().load()
    _hotspot().load()
    return {"status": "retraining_complete", "results": results}


@app.get("/jobs/{job_id}", tags=["Admin"])
async def get_job(job_id: str, _: str = Depends(require_api_key)):
    """Get queued job status from Redis-backed job metadata."""
    job = await service.get_job_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job status not found.")
    return {"job_id": job_id, **job}
