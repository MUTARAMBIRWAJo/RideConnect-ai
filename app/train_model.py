"""train_model.py — Production training pipeline.

Fetches historical ride data from the Supabase PostgreSQL database,
engineers features from the real rides/bookings schema, trains a
RandomForestRegressor, and saves the model to MODEL_PATH.

Usage:
    # From project root (local):
    python -m app.train_model

    # Inside the running container:
    docker exec rideconnect_ai python -m app.train_model
"""

import logging
import math
import os
import sys

import joblib
import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("train_model")

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
MODEL_PATH: str = os.environ.get("MODEL_PATH", "app/price_model.pkl")
MIN_REAL_ROWS: int = 30  # supplement with synthetic data when below this

# ---------------------------------------------------------------------------
# Ride-type encoding — must stay consistent with app/model.py
# ---------------------------------------------------------------------------
RIDE_TYPE_MAP = {"standard": 0, "premium": 1, "boda": 2, "shared": 3}


# ---------------------------------------------------------------------------
# Feature helpers
# ---------------------------------------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    R = 6_371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin(math.radians(lat2 - lat1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(max(a, 0.0)))


def estimate_traffic(hour: int) -> int:
    """Approximate traffic level (1–5) from hour of day."""
    if hour in range(7, 10) or hour in range(17, 20):
        return 4  # AM / PM peak
    if hour in range(22, 24) or hour in range(0, 6):
        return 1  # night
    return 3  # off-peak


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
def fetch_training_data(db_url: str) -> pd.DataFrame:
    """Query rides + booking counts from Supabase."""
    logger.info("Connecting to Supabase …")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # - distance computed from origin/destination coords
    # - demand proxied by confirmed bookings per ride
    # - target: price_per_seat (RWF)
    cur.execute(
        """
        SELECT
            r.id,
            r.origin_lat::float,
            r.origin_lng::float,
            r.destination_lat::float,
            r.destination_lng::float,
            r.price_per_seat::float,
            r.available_seats,
            r.ride_type,
            r.departure_time,
            COUNT(b.id) AS bookings_count
        FROM rides r
        LEFT JOIN bookings b
               ON b.ride_id = r.id
              AND b.status NOT IN ('cancelled', 'failed')
        WHERE
            r.price_per_seat IS NOT NULL
            AND r.origin_lat   IS NOT NULL
            AND r.destination_lat IS NOT NULL
            AND r.status IN ('completed', 'active', 'scheduled')
        GROUP BY r.id
        ORDER BY r.created_at DESC
        LIMIT 5000
        """
    )
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    logger.info("Fetched %d rides from Supabase.", len(rows))
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------
def build_features(df: pd.DataFrame):
    """Return (X, y) arrays from raw ride DataFrame."""
    records = []
    for _, row in df.iterrows():
        try:
            dist = haversine_km(
                float(row["origin_lat"]),
                float(row["origin_lng"]),
                float(row["destination_lat"]),
                float(row["destination_lng"]),
            )
            if dist <= 0:
                continue

            price = float(row["price_per_seat"])
            if price <= 0:
                continue

            cap = max(int(row["available_seats"] or 1), 1)
            bookings = int(row["bookings_count"] or 0)
            demand = min(5, max(1, round(bookings / cap * 5) or 1))

            dt = row["departure_time"]
            hour = dt.hour if hasattr(dt, "hour") else 12
            dow = dt.weekday() if hasattr(dt, "weekday") else 0
            traffic = estimate_traffic(hour)
            ride_type = RIDE_TYPE_MAP.get(
                str(row["ride_type"] or "standard").lower().strip(), 0
            )

            records.append([dist, demand, traffic, ride_type, hour, dow, price])
        except Exception:
            continue

    if not records:
        return np.empty((0, 6)), np.empty(0)

    arr = np.array(records, dtype=float)
    return arr[:, :6], arr[:, 6]  # X, y


# ---------------------------------------------------------------------------
# Synthetic fallback data
# ---------------------------------------------------------------------------
def synthetic_data(n: int = 300):
    """Generate synthetic ride records using East-African pricing heuristics."""
    rng = np.random.default_rng(42)
    dist = rng.uniform(1, 80, n)
    demand = rng.integers(1, 6, n).astype(float)
    traffic = rng.integers(1, 6, n).astype(float)
    ride_type = rng.integers(0, 4, n).astype(float)
    hour = rng.integers(0, 24, n).astype(float)
    dow = rng.integers(0, 7, n).astype(float)
    # Loosely calibrated to RWF ride prices (Kigali)
    price = 800 + dist * 180 + demand * 150 + traffic * 80 + ride_type * 400
    price += rng.normal(0, 200, n)
    price = np.clip(price, 500, 30_000)
    X = np.column_stack([dist, demand, traffic, ride_type, hour, dow])
    return X, price


# ---------------------------------------------------------------------------
# Train + save
# ---------------------------------------------------------------------------
def train_and_save(X: np.ndarray, y: np.ndarray, model_path: str) -> None:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=3,
        n_jobs=-1,
        random_state=42,
    )
    model.fit(X_train, y_train)
    mae = mean_absolute_error(y_test, model.predict(X_test))
    logger.info(
        "Training complete — MAE: %.2f RWF  |  samples: %d  |  features: distance_km, "
        "demand_level, traffic_level, ride_type, hour, day_of_week",
        mae,
        len(X),
    )

    dest_dir = os.path.dirname(os.path.abspath(model_path))
    os.makedirs(dest_dir, exist_ok=True)
    joblib.dump(model, model_path)
    logger.info("Model saved → %s", model_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable is not set.")
        sys.exit(1)

    X_real: np.ndarray = np.empty((0, 6))
    y_real: np.ndarray = np.empty(0)

    try:
        df = fetch_training_data(DATABASE_URL)
        X_real, y_real = build_features(df)
        logger.info("Real training rows after feature engineering: %d", len(y_real))
    except Exception as exc:
        logger.warning("Could not fetch real data (%s). Using synthetic data only.", exc)

    if len(y_real) < MIN_REAL_ROWS:
        need = max(300, MIN_REAL_ROWS * 3)
        logger.info(
            "Supplementing with %d synthetic rows (real=%d < min=%d).",
            need,
            len(y_real),
            MIN_REAL_ROWS,
        )
        X_syn, y_syn = synthetic_data(need)
        X = np.vstack([X_real, X_syn]) if len(y_real) > 0 else X_syn
        y = np.concatenate([y_real, y_syn]) if len(y_real) > 0 else y_syn
    else:
        X, y = X_real, y_real

    train_and_save(X, y, MODEL_PATH)


if __name__ == "__main__":
    main()
