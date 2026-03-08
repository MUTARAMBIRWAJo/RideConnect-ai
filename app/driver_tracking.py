"""driver_tracking.py — Real-time driver GPS management.

Manages driver location updates and nearby-driver queries.
All data is persisted in the driver_locations + driver_status tables.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from app.utils import logger


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin(math.radians(lat2 - lat1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(max(a, 0.0)))


class DriverTracker:
    """Stores and retrieves driver GPS positions via the shared database."""

    async def update_location(
        self,
        db,
        driver_id: int,
        latitude: float,
        longitude: float,
        heading: Optional[float] = None,
        speed_kmh: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Insert a new location row and refresh driver_status.last_seen."""
        await db.execute(
            """
            INSERT INTO driver_locations
                (driver_id, latitude, longitude, heading, speed_kmh, recorded_at)
            VALUES (:driver_id, :lat, :lng, :heading, :speed, NOW())
            """,
            {"driver_id": driver_id, "lat": latitude, "lng": longitude,
             "heading": heading, "speed": speed_kmh},
        )

        # Upsert driver_status
        await db.execute(
            """
            INSERT INTO driver_status (driver_id, status, last_seen)
            VALUES (:driver_id, 'online', NOW())
            ON CONFLICT (driver_id) DO UPDATE
                SET last_seen = NOW(), status = 'online'
            """,
            {"driver_id": driver_id},
        )

        logger.debug("Location updated for driver %d (%.5f, %.5f)", driver_id, latitude, longitude)
        return {"driver_id": driver_id, "latitude": latitude, "longitude": longitude, "status": "updated"}

    async def nearby_drivers(
        self,
        db,
        pickup_lat: float,
        pickup_lng: float,
        radius_km: float = 5.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return drivers whose latest recorded location is within radius_km."""
        try:
            # Pull latest location per driver (within last 15 minutes)
            rows = await db.fetch_all(
                """
                SELECT DISTINCT ON (dl.driver_id)
                       dl.driver_id,
                       dl.latitude,
                       dl.longitude,
                       dl.heading,
                       dl.speed_kmh,
                       dl.recorded_at,
                       ds.status,
                       d.rating,
                       d.total_rides,
                       u.name
                FROM   driver_locations dl
                JOIN   drivers d  ON d.id = dl.driver_id
                JOIN   users   u  ON u.id = d.user_id
                LEFT JOIN driver_status ds ON ds.driver_id = dl.driver_id
                WHERE  dl.recorded_at >= NOW() - INTERVAL '15 minutes'
                  AND  ds.status IN ('online', 'on_trip')
                  AND  d.deleted_at IS NULL
                ORDER  BY dl.driver_id, dl.recorded_at DESC
                LIMIT  200
                """
            )
        except Exception as exc:
            logger.warning("nearby_drivers DB query failed: %s", exc)
            return []

        results = []
        for r in rows:
            dist = _haversine(pickup_lat, pickup_lng, float(r["latitude"]), float(r["longitude"]))
            if dist <= radius_km:
                results.append({
                    "driver_id": r["driver_id"],
                    "name": r["name"],
                    "latitude": float(r["latitude"]),
                    "longitude": float(r["longitude"]),
                    "heading": r["heading"],
                    "speed_kmh": r["speed_kmh"],
                    "status": r["status"] or "online",
                    "rating": float(r["rating"] or 0),
                    "total_rides": r["total_rides"],
                    "distance_km": round(dist, 3),
                    "last_seen": str(r["recorded_at"]),
                })

        results.sort(key=lambda x: x["distance_km"])
        return results[:limit]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_tracker: Optional[DriverTracker] = None


def get_tracker() -> DriverTracker:
    global _tracker
    if _tracker is None:
        _tracker = DriverTracker()
    return _tracker
