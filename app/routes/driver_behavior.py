"""Driver behavior endpoints for idle detection."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app import service
from app.services.idle_detector import get_idle_detector

router = APIRouter()


@router.get("/driver-idle")
async def driver_idle(
    idle_threshold_minutes: int = Query(20, ge=10, le=120),
    movement_radius_m: float = Query(100.0, ge=20.0, le=500.0),
):
    idle = await get_idle_detector().detect(
        db=service.database,
        idle_threshold_minutes=idle_threshold_minutes,
        radius_m=movement_radius_m,
    )
    return {"idle_drivers": idle}
