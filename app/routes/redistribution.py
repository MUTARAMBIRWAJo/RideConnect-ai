"""Driver redistribution endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app import service
from app.model import haversine_km
from app.services.clustering_service import get_clustering_service

router = APIRouter()


async def _active_drivers(limit: int = 120):
    try:
        rows = await service.database.fetch_all(
            "SELECT DISTINCT ON (dl.driver_id) dl.driver_id, dl.latitude::float AS lat, "
            "dl.longitude::float AS lng "
            "FROM driver_locations dl "
            "ORDER BY dl.driver_id, dl.recorded_at DESC LIMIT :limit",
            {"limit": limit},
        )
        return [dict(r) for r in rows]
    except Exception:
        return []


@router.get("/driver-redistribution")
async def driver_redistribution(
    max_suggestions: int = Query(20, ge=1, le=100),
):
    cache_key = f"rideconnect:cache:ai:driver-redistribution:{max_suggestions}"
    cached = await service.cache_get_json(cache_key)
    if cached:
        return cached

    hotspots = await get_clustering_service().predict_hotspots(
        db=service.database,
        weather="clear",
        cluster_count=6,
        horizon_minutes=30,
    )
    drivers = await _active_drivers()

    if not hotspots or not drivers:
        payload = {"suggestions": []}
        await service.cache_set_json(cache_key, payload, ttl_seconds=120)
        return payload

    # Demand-weighted target pool for nearest-neighbor suggestions.
    demand_targets = sorted(hotspots, key=lambda x: x["expected_rides"], reverse=True)
    suggestions = []
    for driver in drivers:
        current_lat = float(driver["lat"])
        current_lng = float(driver["lng"])
        best = min(
            demand_targets,
            key=lambda h: haversine_km(current_lat, current_lng, h["lat"], h["lng"]),
        )
        distance = haversine_km(current_lat, current_lng, best["lat"], best["lng"])
        if distance < 0.3:
            continue

        suggestions.append(
            {
                "driver_id": int(driver["driver_id"]),
                "current_location": {"lat": round(current_lat, 6), "lng": round(current_lng, 6)},
                "suggested_location": {"lat": best["lat"], "lng": best["lng"]},
                "reason": "High demand predicted in this area",
            }
        )

    payload = {"suggestions": suggestions[:max_suggestions]}
    await service.cache_set_json(cache_key, payload, ttl_seconds=120)
    return payload
