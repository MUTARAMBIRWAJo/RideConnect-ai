"""hotspot_detection.py — K-Means clustering for high-demand zone detection.

Clusters historical pickup coordinates into demand hotspots.
Results are stored in the demand_zones table and served via GET /demand-hotspots.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import joblib
import numpy as np

from app.utils import logger

HOTSPOT_MODEL_PATH = os.environ.get("HOTSPOT_MODEL_PATH", "models/hotspot_kmeans.pkl")
DEFAULT_K = int(os.environ.get("HOTSPOT_K", "10"))


class HotspotDetector:
    """Wraps sklearn KMeans. Trains on pickup lat/lng arrays."""

    def __init__(self, model_path: str = HOTSPOT_MODEL_PATH, k: int = DEFAULT_K) -> None:
        self._model = None
        self._path = model_path
        self._k = k
        self._cluster_stats: List[Dict[str, Any]] = []

    @property
    def is_fitted(self) -> bool:
        return self._model is not None

    # ------------------------------------------------------------------
    def load(self) -> None:
        if os.path.exists(self._path):
            try:
                saved = joblib.load(self._path)
                self._model = saved["model"]
                self._cluster_stats = saved.get("stats", [])
                logger.info("Hotspot KMeans loaded from %s  (k=%d)", self._path, self._k)
                return
            except Exception as exc:
                logger.warning("Could not load hotspot model: %s", exc)
        self._bootstrap()

    def _bootstrap(self) -> None:
        """Fit on synthetic Kigali-area pickups so the endpoint works immediately."""
        rng = np.random.default_rng(7)
        centres = np.array([
            [-1.9441, 30.0619], [-1.9403, 30.0888], [-1.9535, 30.1117],
            [-1.9741, 30.0453], [-1.9276, 30.1178], [-1.9109, 30.0619],
            [-2.0000, 30.0800], [-1.9218, 30.0800], [-1.9686, 30.1386],
            [-1.4990, 29.6344],
        ])
        k = min(self._k, len(centres))
        pts_per_centre = 30
        noise = rng.normal(0, 0.008, (k * pts_per_centre, 2))
        X = np.vstack([
            centres[i % k] + noise[i] for i in range(k * pts_per_centre)
        ])
        self.fit(X)

    # ------------------------------------------------------------------
    def fit(self, coords: np.ndarray) -> None:
        """Fit KMeans on Nx2 array of [lat, lng]."""
        from sklearn.cluster import KMeans

        k = min(self._k, len(coords))
        km = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
        km.fit(coords)

        self._model = km
        self._cluster_stats = self._compute_stats(coords, km)

        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        joblib.dump({"model": km, "stats": self._cluster_stats}, self._path)
        logger.info("KMeans fitted (k=%d, inertia=%.2f) → saved %s", k, km.inertia_, self._path)

    @staticmethod
    def _compute_stats(coords: np.ndarray, km) -> List[Dict[str, Any]]:
        labels = km.labels_
        stats = []
        for cid, centre in enumerate(km.cluster_centers_):
            mask = labels == cid
            count = int(mask.sum())
            # Approximate radius: mean distance from centre
            if count > 0:
                diffs = coords[mask] - centre
                radius = float(np.mean(np.sqrt((diffs ** 2).sum(axis=1)))) * 111.0  # deg→km
            else:
                radius = 1.0
            stats.append({
                "cluster_id": cid,
                "center_lat": round(float(centre[0]), 6),
                "center_lng": round(float(centre[1]), 6),
                "ride_count": count,
                "radius_km": round(radius, 3),
                "demand_score": round(min(1.0, count / max(1, len(coords)) * len(km.cluster_centers_)), 4),
            })
        stats.sort(key=lambda x: x["demand_score"], reverse=True)
        return stats

    # ------------------------------------------------------------------
    def get_hotspots(self) -> List[Dict[str, Any]]:
        if not self.is_fitted:
            return []
        return self._cluster_stats

    def predict_cluster(self, lat: float, lng: float) -> Optional[int]:
        """Return which cluster a coordinate belongs to."""
        if not self.is_fitted:
            return None
        return int(self._model.predict([[lat, lng]])[0])


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_detector: Optional[HotspotDetector] = None


def get_detector() -> HotspotDetector:
    global _detector
    if _detector is None:
        _detector = HotspotDetector()
        _detector.load()
    return _detector
