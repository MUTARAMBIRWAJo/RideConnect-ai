"""Demand hotspot endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app import service
from app.services.clustering_service import get_clustering_service

router = APIRouter()


@router.get("/demand-hotspots")
async def demand_hotspots(
    limit: int = Query(10, ge=1, le=50),
    weather: str = Query("clear"),
    horizon_minutes: int = Query(30, ge=15, le=30),
):
    cache_key = f"rideconnect:cache:ai:demand-hotspots:{limit}:{weather}:{horizon_minutes}"
    cached = await service.cache_get_json(cache_key)
    if cached:
        return cached

    hotspots = await get_clustering_service().predict_hotspots(
        db=service.database,
        weather=weather,
        cluster_count=min(6, limit),
        horizon_minutes=horizon_minutes,
    )
    payload = {"hotspots": hotspots[:limit]}
    await service.cache_set_json(cache_key, payload, ttl_seconds=120)
    return payload
