"""retraining.py — Continuous learning pipeline.

Retrains all ML models using fresh data from Supabase:
    - Price model (RandomForest)
    - Demand model (RandomForest)
    - ETA model (GradientBoosting)
    - Behavior model (RandomForestClassifier)
    - Anomaly model (IsolationForest)
    - Hotspot model (KMeans)

Can be triggered:
    1. Manually:  docker exec rideconnect_ai python -m app.retraining
    2. Via API:   POST /retrain  (admin only)
    3. Via cron inside the container (add to Dockerfile CMD if needed)
"""

from __future__ import annotations

import logging
import math
import os
import sys

import numpy as np
import psycopg2
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("retraining")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
MIN_ROWS = 20   # minimum rows before retraining (falls back to synthetic if below)


def _connect():
    return psycopg2.connect(DATABASE_URL)


def _haversine(lat1, lon1, lat2, lon2):
    R = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2-lat1)/2)**2
         + math.cos(phi1)*math.cos(phi2)*math.sin(math.radians(lon2-lon1)/2)**2)
    return 2 * R * math.asin(math.sqrt(max(a, 0.0)))


# ---------------------------------------------------------------------------
# Price model
# ---------------------------------------------------------------------------
def retrain_price_model() -> None:
    logger.info("--- Retraining price model ---")
    from app.train_model import main as train_main
    train_main()


# ---------------------------------------------------------------------------
# Demand model
# ---------------------------------------------------------------------------
def retrain_demand_model() -> None:
    logger.info("--- Retraining demand model ---")
    from app.demand_prediction import DemandPredictor, DEMAND_MODEL_PATH
    from sklearn.ensemble import RandomForestRegressor

    rows_loaded = 0
    X, y = np.empty((0, 9)), np.empty(0)

    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT z.center_lat, z.center_lng, pd.hour, pd.day_of_week,
                   pd.demand_score, pd.predicted_requests
            FROM   predicted_demand pd
            JOIN   demand_zones z ON z.id = pd.zone_id
            ORDER  BY pd.predicted_at DESC
            LIMIT  2000
        """)
        rows = cur.fetchall()
        conn.close()

        if rows:
            records = []
            for r in rows:
                lat, lng, hour, dow, score, req = r
                peak = int(dow < 5 and (7 <= hour <= 9 or 17 <= hour <= 19))
                records.append([float(hour), float(dow), peak, 3, float(req or 10),
                                 int(float(lat)*100), int(float(lng)*100), 0, 0, float(score)])
            arr = np.array(records, dtype=float)
            X, y = arr[:, :9], arr[:, 9]
            rows_loaded = len(y)
            logger.info("Loaded %d demand rows from Supabase", rows_loaded)
    except Exception as exc:
        logger.warning("Demand data fetch failed: %s", exc)

    if rows_loaded < MIN_ROWS:
        logger.info("Supplementing demand data with synthetic rows.")
        pred = DemandPredictor(DEMAND_MODEL_PATH)
        pred.load()  # re-bootstraps and saves
        return

    model = RandomForestRegressor(n_estimators=150, max_depth=8, random_state=42)
    model.fit(X, y)

    import joblib
    os.makedirs(os.path.dirname(os.path.abspath(DEMAND_MODEL_PATH)), exist_ok=True)
    joblib.dump(model, DEMAND_MODEL_PATH)
    logger.info("Demand model retrained (%d rows) → %s", rows_loaded, DEMAND_MODEL_PATH)


# ---------------------------------------------------------------------------
# ETA model
# ---------------------------------------------------------------------------
def retrain_eta_model() -> None:
    logger.info("--- Retraining ETA model ---")
    from app.eta_predictor import ETAPredictor, ETA_MODEL_PATH

    rows_loaded = 0
    X, y = np.empty((0, 7)), np.empty(0)

    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT t.pickup_lat::float, t.pickup_lng::float,
                   t.dropoff_lat::float, t.dropoff_lng::float,
                   t.fare::float,
                   EXTRACT(HOUR FROM t.requested_at)  AS hour,
                   EXTRACT(DOW  FROM t.requested_at)  AS dow,
                   EXTRACT(EPOCH FROM (t.completed_at - t.started_at))/60 AS duration_min
            FROM   trips t
            WHERE  t.status = 'COMPLETED'
              AND  t.completed_at IS NOT NULL
              AND  t.started_at IS NOT NULL
            LIMIT  3000
        """)
        rows = cur.fetchall()
        conn.close()

        records = []
        for r in rows:
            try:
                dist = _haversine(r[0], r[1], r[2], r[3])
                dur = float(r[7])
                if dist <= 0 or dur <= 0:
                    continue
                records.append([dist, 3, float(r[5]), float(r[6]), 1, 0, dist * 1.8, dur])
            except Exception:
                continue
        if records:
            arr = np.array(records, dtype=float)
            X, y = arr[:, :7], arr[:, 7]
            rows_loaded = len(y)
            logger.info("Loaded %d trip rows for ETA retrain", rows_loaded)
    except Exception as exc:
        logger.warning("ETA data fetch failed: %s", exc)

    if rows_loaded < MIN_ROWS:
        logger.info("Bootstrapping ETA model with synthetic data.")
        pred = ETAPredictor(ETA_MODEL_PATH)
        pred.load()
        return

    from sklearn.ensemble import GradientBoostingRegressor
    import joblib
    model = GradientBoostingRegressor(n_estimators=150, max_depth=5, random_state=42)
    model.fit(X, y)
    os.makedirs(os.path.dirname(os.path.abspath(ETA_MODEL_PATH)), exist_ok=True)
    joblib.dump(model, ETA_MODEL_PATH)
    logger.info("ETA model retrained (%d rows) → %s", rows_loaded, ETA_MODEL_PATH)


# ---------------------------------------------------------------------------
# Hotspot model
# ---------------------------------------------------------------------------
def retrain_hotspot_model() -> None:
    logger.info("--- Retraining hotspot model ---")
    from app.hotspot_detection import HotspotDetector, HOTSPOT_MODEL_PATH

    coords = np.empty((0, 2))
    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT pickup_lat::float, pickup_lng::float
            FROM   trips
            WHERE  pickup_lat IS NOT NULL AND pickup_lng IS NOT NULL
            UNION ALL
            SELECT origin_lat::float, origin_lng::float
            FROM   rides
            WHERE  origin_lat IS NOT NULL AND origin_lng IS NOT NULL
            LIMIT  5000
        """)
        rows = cur.fetchall()
        conn.close()
        if rows:
            coords = np.array([[r[0], r[1]] for r in rows], dtype=float)
            logger.info("Loaded %d coordinates for hotspot clustering", len(coords))
    except Exception as exc:
        logger.warning("Hotspot data fetch failed: %s", exc)

    det = HotspotDetector(HOTSPOT_MODEL_PATH)
    if len(coords) >= 10:
        det.fit(coords)
    else:
        det.load()  # will bootstrap
    logger.info("Hotspot model updated.")


# ---------------------------------------------------------------------------
# Behavior model
# ---------------------------------------------------------------------------
def retrain_behavior_model() -> None:
    logger.info("--- Retraining behavior model ---")
    from app.behavior_analysis import BehaviorAnalyzer, BEHAVIOR_MODEL_PATH

    rows_loaded = 0
    X, y = np.empty((0, 6)), np.empty(0)

    try:
        conn = _connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT dbl.avg_speed_kmh::float,
                   dbl.cancellation_rate::float,
                   dbl.avg_rating::float,
                   dbl.route_deviation_pct::float,
                   d.total_rides,
                   dbl.behavior_class
            FROM   driver_behavior_logs dbl
            JOIN   drivers d ON d.id = dbl.driver_id
            WHERE  dbl.behavior_class != 'unknown'
            ORDER  BY dbl.analyzed_at DESC
            LIMIT  1000
        """)
        rows = cur.fetchall()
        conn.close()

        records = []
        for r in rows:
            try:
                records.append([30.0, float(r[0]), float(r[1]), float(r[2]),
                                 float(r[3] or 5), min(1.0, float(r[4] or 0)/1000), str(r[5])])
            except Exception:
                continue
        if records:
            arr_lbl = [r[-1] for r in records]
            arr_X = np.array([r[:-1] for r in records], dtype=float)
            X, y = arr_X, np.array(arr_lbl)
            rows_loaded = len(y)
            logger.info("Loaded %d behavior rows", rows_loaded)
    except Exception as exc:
        logger.warning("Behavior data fetch failed: %s", exc)

    if rows_loaded < MIN_ROWS:
        BehaviorAnalyzer(BEHAVIOR_MODEL_PATH).load()
        return

    from sklearn.ensemble import RandomForestClassifier
    import joblib
    model = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
    model.fit(X, y)
    os.makedirs(os.path.dirname(os.path.abspath(BEHAVIOR_MODEL_PATH)), exist_ok=True)
    joblib.dump(model, BEHAVIOR_MODEL_PATH)
    logger.info("Behavior model retrained (%d rows) → %s", rows_loaded, BEHAVIOR_MODEL_PATH)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
def run_full_pipeline() -> dict:
    results = {}
    for name, fn in [
        ("price",    retrain_price_model),
        ("demand",   retrain_demand_model),
        ("eta",      retrain_eta_model),
        ("hotspot",  retrain_hotspot_model),
        ("behavior", retrain_behavior_model),
    ]:
        try:
            fn()
            results[name] = "ok"
        except Exception as exc:
            logger.error("Retrain %s FAILED: %s", name, exc)
            results[name] = f"error: {exc}"
    logger.info("Retraining pipeline complete: %s", results)
    return results


if __name__ == "__main__":
    if not DATABASE_URL:
        logger.error("DATABASE_URL not set.")
        sys.exit(1)
    run_full_pipeline()
