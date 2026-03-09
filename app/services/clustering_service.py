"""Demand hotspot clustering and scoring service."""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional

import numpy as np
from sklearn.cluster import KMeans

from app.models.demand_model import get_demand_lstm_model


class ClusteringService:
    def __init__(self) -> None:
        self._demand_model = get_demand_lstm_model()

    async def _seed_points_from_db(self, db) -> List[Dict]:
        # Prefer explicit demand zones when available.
        try:
            rows = await db.fetch_all(
                "SELECT center_lat::float AS lat, center_lng::float AS lng, "
                "COALESCE(ride_count, 20) AS historical_count "
                "FROM demand_zones WHERE active=TRUE LIMIT 80"
            )
            if rows:
                return [
                    {
                        "lat": float(r["lat"]),
                        "lng": float(r["lng"]),
                        "historical_count": int(r["historical_count"] or 20),
                    }
                    for r in rows
                ]
        except Exception:
            pass

        # Fallback to known Kigali strategic points.
        return [
            {"lat": -1.9441, "lng": 30.0619, "historical_count": 35},
            {"lat": -1.9536, "lng": 30.1044, "historical_count": 28},
            {"lat": -1.9706, "lng": 30.1044, "historical_count": 19},
            {"lat": -1.9398, "lng": 30.0838, "historical_count": 24},
            {"lat": -1.9264, "lng": 30.1197, "historical_count": 22},
            {"lat": -1.9838, "lng": 30.1405, "historical_count": 15},
            {"lat": -1.9513, "lng": 30.0588, "historical_count": 27},
            {"lat": -1.9487, "lng": 30.0903, "historical_count": 30},
        ]

    async def predict_hotspots(
        self,
        db,
        weather: str = "clear",
        cluster_count: int = 5,
        horizon_minutes: int = 30,
        day_of_week: Optional[int] = None,
        hour: Optional[int] = None,
    ) -> List[Dict]:
        points = await self._seed_points_from_db(db)
        if not points:
            return []

        coords = np.array([[p["lat"], p["lng"]] for p in points], dtype=float)
        k = min(max(1, cluster_count), len(points))
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(coords)

        now = datetime.datetime.now()
        h = now.hour if hour is None else hour
        dow = now.weekday() if day_of_week is None else day_of_week

        hotspots: List[Dict] = []
        for cid, center in enumerate(km.cluster_centers_):
            members = [points[i] for i in range(len(points)) if labels[i] == cid]
            if not members:
                continue
            hist = max(1, int(np.mean([m["historical_count"] for m in members])))
            pred = self._demand_model.predict_next_window(
                lat=float(center[0]),
                lng=float(center[1]),
                historical_count=hist,
                weather=weather,
                hour=h,
                day_of_week=dow,
                traffic_level=3,
                event_indicator=0,
            )

            scale = 1.0 if horizon_minutes <= 20 else 1.2
            expected = int(round(pred["expected_rides"] * scale))
            hotspots.append(
                {
                    "lat": round(float(center[0]), 6),
                    "lng": round(float(center[1]), 6),
                    "demand_score": round(float(pred["demand_score"]), 4),
                    "expected_rides": max(1, expected),
                }
            )

        hotspots.sort(key=lambda x: (x["demand_score"], x["expected_rides"]), reverse=True)
        return hotspots


_service = ClusteringService()


def get_clustering_service() -> ClusteringService:
    return _service
