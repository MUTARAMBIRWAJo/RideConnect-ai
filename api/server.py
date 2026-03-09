"""Standalone FastAPI server for RideConnect custom AI microservice."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routes.demand import router as demand_router
from api.routes.eta import router as eta_router
from api.routes.matching import router as matching_router
from api.routes.pricing import router as pricing_router
from utils.logger import get_logger

logger = get_logger("rideconnect_ai_server")

app = FastAPI(
    title="RideConnect AI Service",
    version="3.0.0",
    description="Custom algorithmic AI microservice for matching, pricing, ETA, and demand.",
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "detail": "Internal server error"},
    )


@app.get("/")
def root() -> dict:
    return {
        "service": "RideConnect AI",
        "status": "running",
        "version": "3.0.0",
        "docs": "/docs",
    }


app.include_router(matching_router, prefix="/ai", tags=["Matching AI"])
app.include_router(pricing_router, prefix="/ai", tags=["Pricing AI"])
app.include_router(eta_router, prefix="/ai", tags=["ETA AI"])
app.include_router(demand_router, prefix="/ai", tags=["Demand AI"])
