"""Traffic-aware route monitoring endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.route_monitor import get_route_monitor

router = APIRouter()


class RouteMonitorRequest(BaseModel):
    driver_lat: float
    driver_lng: float
    destination_lat: float
    destination_lng: float


@router.post("/route-monitor")
async def route_monitor(body: RouteMonitorRequest):
    return get_route_monitor().monitor(
        driver_lat=body.driver_lat,
        driver_lng=body.driver_lng,
        destination_lat=body.destination_lat,
        destination_lng=body.destination_lng,
    )
