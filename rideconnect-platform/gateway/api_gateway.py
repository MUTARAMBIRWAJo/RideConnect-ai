"""API gateway orchestrating ride lifecycle across microservices and streams."""

from __future__ import annotations

import os
import uuid
import asyncio
import time
import json
from datetime import datetime, timezone
from collections import defaultdict
from functools import lru_cache
from typing import Dict, List

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from geo.city_zones import load_city_config, resolve_zone
from streaming.kafka_producer import RideEventProducer

try:
    import redis.asyncio as redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None

app = FastAPI(title="RideConnect API Gateway", version="1.0.0")
producer = RideEventProducer()
async_client: httpx.AsyncClient | None = None
redis_client: "redis.Redis | None" = None

DISPATCH_URL = os.getenv("DISPATCH_SERVICE_URL", "http://dispatch-service:8101")
PRICING_URL = os.getenv("PRICING_SERVICE_URL", "http://pricing-service:8102")
ETA_URL = os.getenv("ETA_SERVICE_URL", "http://eta-service:8103")
DEMAND_URL = os.getenv("DEMAND_SERVICE_URL", "http://demand-service:8104")
DISPATCH_TIMEOUT_MS = int(os.getenv("DISPATCH_TIMEOUT_MS", "450"))
ETA_TIMEOUT_MS = int(os.getenv("ETA_TIMEOUT_MS", "450"))
PRICING_TIMEOUT_MS = int(os.getenv("PRICING_TIMEOUT_MS", "450"))
RIDE_RESPONSE_CACHE_TTL_MS = int(os.getenv("RIDE_RESPONSE_CACHE_TTL_MS", "1200"))
RIDE_RESPONSE_CACHE_MAX = int(os.getenv("RIDE_RESPONSE_CACHE_MAX", "4000"))
REDIS_URL = os.getenv("REDIS_URL", "")
REDIS_CACHE_PREFIX = os.getenv("REDIS_CACHE_PREFIX", "rideconnect:gateway")
COALESCE_WAIT_MS = int(os.getenv("COALESCE_WAIT_MS", "220"))

TOPIC_MAP = {
    "driver_location_updates": "driver_locations",
    "ride_requested": "ride_requests",
    "ride_assigned": "ride_status",
    "ride_started": "ride_status",
    "ride_completed": "ride_status",
    "ride_cancelled": "ride_status",
}

# Per-process cache/coalescing structures (effective with gateway workers).
_response_cache: Dict[str, tuple[float, Dict]] = {}
_inflight: Dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()
_metrics = defaultdict(int)


@lru_cache(maxsize=16)
def _city_config(city_id: str) -> Dict:
    return load_city_config(city_id)


def _request_cache_key(body: "RideRequest") -> str:
    return (
        f"{body.city_id}|{round(body.pickup_lat, 4)}|{round(body.pickup_lng, 4)}|"
        f"{round(body.destination_lat, 4)}|{round(body.destination_lng, 4)}|{len(body.candidate_drivers)}"
    )


def _cache_get(key: str) -> Dict | None:
    item = _response_cache.get(key)
    if item is None:
        return None
    expires_at, payload = item
    if time.monotonic() > expires_at:
        _response_cache.pop(key, None)
        return None
    _metrics["cache_hits"] += 1
    return payload


def _cache_set(key: str, payload: Dict) -> None:
    if len(_response_cache) >= RIDE_RESPONSE_CACHE_MAX:
        # Remove an arbitrary stale key to cap memory usage.
        _response_cache.pop(next(iter(_response_cache)), None)
        _metrics["cache_evictions"] += 1
    ttl_sec = max(0.1, RIDE_RESPONSE_CACHE_TTL_MS / 1000.0)
    _response_cache[key] = (time.monotonic() + ttl_sec, payload)


async def _redis_cache_get(key: str) -> Dict | None:
    if redis_client is None:
        return None
    try:
        raw = await redis_client.get(f"{REDIS_CACHE_PREFIX}:resp:{key}")
        if not raw:
            return None
        _metrics["redis_cache_hits"] += 1
        return json.loads(raw)
    except Exception:
        return None


async def _redis_cache_set(key: str, payload: Dict) -> None:
    if redis_client is None:
        return
    try:
        ttl_sec = max(1, int(RIDE_RESPONSE_CACHE_TTL_MS / 1000.0))
        await redis_client.setex(f"{REDIS_CACHE_PREFIX}:resp:{key}", ttl_sec, json.dumps(payload))
    except Exception:
        return


async def _redis_try_lock(key: str, token: str) -> bool:
    if redis_client is None:
        return False
    try:
        lock_ttl = max(1, int((DISPATCH_TIMEOUT_MS + ETA_TIMEOUT_MS + PRICING_TIMEOUT_MS) / 1000.0) + 1)
        return bool(await redis_client.set(f"{REDIS_CACHE_PREFIX}:lock:{key}", token, ex=lock_ttl, nx=True))
    except Exception:
        return False


async def _redis_unlock(key: str, token: str) -> None:
    if redis_client is None:
        return
    script = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )
    try:
        await redis_client.eval(script, 1, f"{REDIS_CACHE_PREFIX}:lock:{key}", token)
    except Exception:
        return


async def _redis_wait_for_cached(key: str, wait_ms: int, poll_ms: int = 25) -> Dict | None:
    deadline = time.monotonic() + (wait_ms / 1000.0)
    while time.monotonic() < deadline:
        cached = await _redis_cache_get(key)
        if cached is not None:
            _metrics["redis_wait_hits"] += 1
            return cached
        await asyncio.sleep(max(0.005, poll_ms / 1000.0))
    return None


class DriverSnapshot(BaseModel):
    driver_id: str
    lat: float
    lng: float
    rating: float = 4.0
    available: bool = True


class RideRequest(BaseModel):
    city_id: str
    rider_id: str
    pickup_lat: float
    pickup_lng: float
    destination_lat: float
    destination_lng: float
    candidate_drivers: List[DriverSnapshot] = Field(default_factory=list)


def _degraded_assignment(ride_id: str) -> Dict:
    return {"status": "pending_assignment", "ride_id": ride_id, "driver_id": None, "score": 0.0}


def _degraded_eta(city_id: str) -> Dict:
    return {
        "city_id": city_id,
        "algorithm": "fallback",
        "predicted_eta_minutes": 18.0,
        "route": [],
    }


def _degraded_pricing(city_id: str) -> Dict:
    return {
        "city_id": city_id,
        "zone_id": "unknown",
        "predicted_price": 2500.0,
        "currency": "RWF" if city_id == "kigali" else ("KES" if city_id == "nairobi" else "NGN"),
        "surge_multiplier": 1.0,
    }


async def _call_json(task: asyncio.Future, timeout_ms: int) -> Dict | None:
    try:
        resp = await asyncio.wait_for(task, timeout=timeout_ms / 1000.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


@app.get("/v1/health")
def health() -> Dict:
    return {
        "status": "ok",
        "service": "gateway",
        "kafka_bootstrap": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "cache": {
            "entries": len(_response_cache),
            "ttl_ms": RIDE_RESPONSE_CACHE_TTL_MS,
            "hits": _metrics["cache_hits"],
            "evictions": _metrics["cache_evictions"],
            "redis_hits": _metrics["redis_cache_hits"],
            "redis_wait_hits": _metrics["redis_wait_hits"],
        },
        "timeouts": {
            "dispatch": _metrics["timeout_dispatch"],
            "eta": _metrics["timeout_eta"],
            "pricing": _metrics["timeout_pricing"],
        },
        "partial_responses": _metrics["partial_responses"],
        "coalesced_requests": _metrics["coalesced_requests"],
        "inflight_requests": len(_inflight),
        "redis_connected": redis_client is not None,
    }


@app.on_event("startup")
async def _startup() -> None:
    global async_client, redis_client
    limits = httpx.Limits(max_connections=400, max_keepalive_connections=120)
    async_client = httpx.AsyncClient(timeout=1.5, limits=limits)
    if redis is not None and REDIS_URL:
        try:
            redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            await redis_client.ping()
        except Exception:
            redis_client = None


@app.on_event("shutdown")
async def _shutdown() -> None:
    global async_client, redis_client
    if async_client is not None:
        await async_client.aclose()
        async_client = None
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


@app.post("/v1/events/{event_type}")
def ingest_event(event_type: str, payload: Dict) -> Dict:
    if event_type not in TOPIC_MAP:
        raise HTTPException(status_code=400, detail=f"Unsupported event type: {event_type}")
    topic = TOPIC_MAP[event_type]
    event = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    result = producer.publish_event(topic, event)
    return {"status": "accepted", "topic": topic, **result}


@app.post("/v1/rides/request")
async def request_ride(body: RideRequest) -> Dict:
    key = _request_cache_key(body)

    cached_redis = await _redis_cache_get(key)
    if cached_redis is not None:
        return {**cached_redis, "cached": True, "cache_backend": "redis"}

    cached = _cache_get(key)
    if cached is not None:
        return {**cached, "cached": True, "cache_backend": "local"}

    lock_token = str(uuid.uuid4())
    got_distributed_lock = await _redis_try_lock(key, lock_token)
    if redis_client is not None and not got_distributed_lock:
        waited = await _redis_wait_for_cached(key, wait_ms=COALESCE_WAIT_MS)
        if waited is not None:
            _metrics["coalesced_requests"] += 1
            return {**waited, "cached": True, "coalesced": True, "cache_backend": "redis"}

    promise: asyncio.Future | None = None
    async with _inflight_lock:
        existing = _inflight.get(key)
        if existing is None:
            loop = asyncio.get_running_loop()
            promise = loop.create_future()
            _inflight[key] = promise

    if existing is not None:
        _metrics["coalesced_requests"] += 1
        result = await existing
        return {**result, "coalesced": True, "cache_backend": "local"}

    # Multi-city routing guard: city config must exist.
    _city_config(body.city_id)

    ride_id = f"ride-{uuid.uuid4()}"
    zone_id = resolve_zone(body.city_id, body.pickup_lat, body.pickup_lng)

    requested = {
        "event_type": "ride_requested",
        "city_id": body.city_id,
        "zone_id": zone_id,
        "ride_id": ride_id,
        "rider_id": body.rider_id,
        "pickup_lat": body.pickup_lat,
        "pickup_lng": body.pickup_lng,
        "destination_lat": body.destination_lat,
        "destination_lng": body.destination_lng,
    }
    producer.publish_event("ride_requests", requested)

    if async_client is None:
        raise HTTPException(status_code=503, detail="Gateway client not initialized")

    dispatch_task = asyncio.create_task(async_client.post(
        f"{DISPATCH_URL}/dispatch/assign",
        json={
            "city_id": body.city_id,
            "ride_id": ride_id,
            "passenger_lat": body.pickup_lat,
            "passenger_lng": body.pickup_lng,
            "drivers": [d.model_dump() for d in body.candidate_drivers],
        },
    ))
    eta_task = asyncio.create_task(async_client.post(
        f"{ETA_URL}/eta/predict",
        json={
            "city_id": body.city_id,
            "origin_lat": body.pickup_lat,
            "origin_lng": body.pickup_lng,
            "destination_lat": body.destination_lat,
            "destination_lng": body.destination_lng,
            "traffic_level": 0.5,
            "algorithm": "astar",
        },
    ))

    try:
        dispatch = await _call_json(dispatch_task, timeout_ms=DISPATCH_TIMEOUT_MS)
        eta = await _call_json(eta_task, timeout_ms=ETA_TIMEOUT_MS)

        assignment = dispatch if dispatch is not None else _degraded_assignment(ride_id)
        eta = eta if eta is not None else _degraded_eta(body.city_id)

        pricing_task = asyncio.create_task(async_client.post(
            f"{PRICING_URL}/pricing/predict",
            json={
                "city_id": body.city_id,
                "pickup_lat": body.pickup_lat,
                "pickup_lng": body.pickup_lng,
                "distance_km": 4.5,
                "duration_min": eta.get("predicted_eta_minutes", 15),
                "demand_level": 0.6,
                "traffic_level": 0.5,
                "hour": datetime.now().hour,
            },
        ))
        pricing = await _call_json(pricing_task, timeout_ms=PRICING_TIMEOUT_MS)
        price = pricing if pricing is not None else _degraded_pricing(body.city_id)

        degraded_services = []
        if dispatch is None:
            degraded_services.append("dispatch")
            _metrics["timeout_dispatch"] += 1
        if eta is None or eta.get("algorithm") == "fallback":
            degraded_services.append("eta")
            _metrics["timeout_eta"] += 1
        if pricing is None:
            degraded_services.append("pricing")
            _metrics["timeout_pricing"] += 1

        partial = bool(degraded_services)
        if partial:
            _metrics["partial_responses"] += 1

        payload = {
            "status": "ok",
            "ride_id": ride_id,
            "city_id": body.city_id,
            "zone_id": zone_id,
            "assignment": assignment,
            "eta": eta,
            "pricing": price,
            "partial_response": partial,
            "degraded_services": degraded_services,
        }
        _cache_set(key, payload)
        await _redis_cache_set(key, payload)
        if promise is not None and not promise.done():
            promise.set_result(payload)
        return payload
    except Exception as exc:
        if promise is not None and not promise.done():
            promise.set_exception(exc)
        raise
    finally:
        if got_distributed_lock:
            await _redis_unlock(key, lock_token)
        async with _inflight_lock:
            if promise is not None:
                _inflight.pop(key, None)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8100")))
