"""Driver idle detection service."""

from __future__ import annotations

import datetime
from typing import Dict, List

from app.model import haversine_km


class IdleDetector:
    async def _latest_locations(self, db) -> List[Dict]:
        try:
            rows = await db.fetch_all(
                "SELECT DISTINCT ON (dl.driver_id) dl.driver_id, dl.latitude::float AS lat, "
                "dl.longitude::float AS lng, dl.recorded_at "
                "FROM driver_locations dl "
                "ORDER BY dl.driver_id, dl.recorded_at DESC LIMIT 400"
            )
            return [dict(r) for r in rows]
        except Exception:
            return []

    async def _movement_radius_m(self, db, driver_id: int, window_minutes: int = 20) -> float:
        try:
            rows = await db.fetch_all(
                "SELECT latitude::float AS lat, longitude::float AS lng "
                "FROM driver_locations "
                "WHERE driver_id=:driver_id AND recorded_at >= NOW() - (:mins || ' minutes')::interval "
                "ORDER BY recorded_at DESC LIMIT 20",
                {"driver_id": driver_id, "mins": window_minutes},
            )
        except Exception:
            return 0.0

        pts = [dict(r) for r in rows]
        if len(pts) < 2:
            return 0.0

        anchor = pts[0]
        distances_m = [
            haversine_km(anchor["lat"], anchor["lng"], p["lat"], p["lng"]) * 1000.0
            for p in pts[1:]
        ]
        return max(distances_m) if distances_m else 0.0

    async def _last_ride_map(self, db) -> Dict[int, datetime.datetime]:
        # Prefer trip timestamps if table supports driver_id.
        try:
            rows = await db.fetch_all(
                "SELECT driver_id, MAX(COALESCE(completed_at, requested_at)) AS last_ride_at "
                "FROM trips WHERE driver_id IS NOT NULL GROUP BY driver_id"
            )
            return {
                int(r["driver_id"]): r["last_ride_at"].replace(tzinfo=None)
                for r in rows
                if r["last_ride_at"] is not None
            }
        except Exception:
            return {}

    async def detect(self, db, idle_threshold_minutes: int = 20, radius_m: float = 100.0) -> List[Dict]:
        latest = await self._latest_locations(db)
        if not latest:
            return []

        last_ride = await self._last_ride_map(db)
        now = datetime.datetime.utcnow()
        idle_rows: List[Dict] = []

        for row in latest:
            driver_id = int(row["driver_id"])
            last_seen = row["recorded_at"].replace(tzinfo=None)
            last_ride_at = last_ride.get(driver_id, last_seen)
            idle_minutes = max(0.0, (now - last_ride_at).total_seconds() / 60.0)

            movement = await self._movement_radius_m(db, driver_id, window_minutes=idle_threshold_minutes)
            if idle_minutes > idle_threshold_minutes and movement <= radius_m:
                idle_rows.append(
                    {
                        "driver_id": driver_id,
                        "idle_minutes": int(round(idle_minutes)),
                        "location": {
                            "lat": round(float(row["lat"]), 6),
                            "lng": round(float(row["lng"]), 6),
                        },
                    }
                )

        idle_rows.sort(key=lambda x: x["idle_minutes"], reverse=True)
        return idle_rows


_detector = IdleDetector()


def get_idle_detector() -> IdleDetector:
    return _detector
