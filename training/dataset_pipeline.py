"""Dataset extraction pipeline using RideConnect platform data only."""

from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2

DATASET_PATH = Path("datasets/rides_dataset.csv")


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(max(a, 0.0)))


def _table_exists(conn: psycopg2.extensions.connection, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            (table_name,),
        )
        return bool(cur.fetchone()[0])


def extract_and_build_dataset(output_path: Path | str = DATASET_PATH, limit: int = 20000) -> pd.DataFrame:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    conn = psycopg2.connect(database_url)

    trips_df = pd.read_sql(
        f"SELECT * FROM trips ORDER BY created_at DESC LIMIT {int(limit)}",
        conn,
    )

    if trips_df.empty:
        raise RuntimeError("No trip rows found for dataset generation")

    # Normalize schema variants.
    trips_df["pickup_lat"] = pd.to_numeric(trips_df.get("pickup_lat"), errors="coerce")
    trips_df["pickup_lng"] = pd.to_numeric(trips_df.get("pickup_lng"), errors="coerce")
    trips_df["dropoff_lat"] = pd.to_numeric(trips_df.get("dropoff_lat"), errors="coerce")
    trips_df["dropoff_lng"] = pd.to_numeric(trips_df.get("dropoff_lng"), errors="coerce")

    trips_df["request_time"] = pd.to_datetime(
        trips_df.get("requested_at", trips_df.get("created_at")),
        errors="coerce",
        utc=True,
    )
    trips_df["driver_assigned_time"] = pd.to_datetime(
        trips_df.get("accepted_at"),
        errors="coerce",
        utc=True,
    )
    trips_df["pickup_time"] = pd.to_datetime(
        trips_df.get("started_at"),
        errors="coerce",
        utc=True,
    )
    trips_df["dropoff_time"] = pd.to_datetime(
        trips_df.get("completed_at"),
        errors="coerce",
        utc=True,
    )

    trips_df["ride_status"] = trips_df.get("status", "unknown").astype(str).str.lower()

    trips_df["ride_duration"] = (
        trips_df["dropoff_time"] - trips_df["pickup_time"]
    ).dt.total_seconds()
    trips_df["ride_duration"] = trips_df["ride_duration"].where(trips_df["ride_duration"] > 0)

    trips_df["ride_distance"] = trips_df.apply(
        lambda row: _haversine_km(
            float(row["pickup_lat"]),
            float(row["pickup_lng"]),
            float(row["dropoff_lat"]),
            float(row["dropoff_lng"]),
        )
        if pd.notna(row["pickup_lat"])
        and pd.notna(row["pickup_lng"])
        and pd.notna(row["dropoff_lat"])
        and pd.notna(row["dropoff_lng"])
        else np.nan,
        axis=1,
    )

    trips_df["distance"] = trips_df["ride_distance"].fillna(0.0)
    trips_df["estimated_time"] = np.where(
        trips_df["distance"] > 0,
        (trips_df["distance"] / 28.0) * 60.0,
        np.nan,
    )

    trips_df["time_of_day"] = trips_df["request_time"].dt.hour.fillna(12).astype(int)
    trips_df["day_of_week"] = trips_df["request_time"].dt.dayofweek.fillna(0).astype(int)

    trips_df["zone_key"] = (
        trips_df["pickup_lat"].round(2).astype(str) + ":" + trips_df["pickup_lng"].round(2).astype(str)
    )

    trips_df["hour_bucket"] = trips_df["request_time"].dt.floor("h")
    trips_df["demand_density"] = (
        trips_df.groupby(["zone_key", "hour_bucket"]) ["id"]
        .transform("count")
        .fillna(1)
        .astype(float)
    )

    if _table_exists(conn, "driver_locations"):
        driver_df = pd.read_sql("SELECT driver_id, latitude, longitude, updated_at FROM driver_locations", conn)
        if not driver_df.empty:
            driver_df["zone_key"] = (
                pd.to_numeric(driver_df["latitude"], errors="coerce").round(2).astype(str)
                + ":"
                + pd.to_numeric(driver_df["longitude"], errors="coerce").round(2).astype(str)
            )
            driver_density = driver_df.groupby("zone_key")["driver_id"].nunique().rename("driver_density")
            trips_df = trips_df.merge(driver_density, on="zone_key", how="left")
        else:
            trips_df["driver_density"] = 1.0
    else:
        trips_df["driver_density"] = 1.0

    trips_df["driver_density"] = pd.to_numeric(trips_df["driver_density"], errors="coerce").fillna(1.0)

    if _table_exists(conn, "traffic_events"):
        traffic_df = pd.read_sql("SELECT traffic_level, weather_factor, event_time FROM traffic_events", conn)
        if not traffic_df.empty:
            traffic_df["event_time"] = pd.to_datetime(traffic_df["event_time"], errors="coerce", utc=True)
            traffic_df["hour_bucket"] = traffic_df["event_time"].dt.floor("h")
            traffic_agg = traffic_df.groupby("hour_bucket").agg(
                traffic_level=("traffic_level", "mean"),
                weather=("weather_factor", "mean"),
            )
            trips_df = trips_df.merge(traffic_agg, on="hour_bucket", how="left")
        else:
            trips_df["traffic_level"] = 0.35
            trips_df["weather"] = 1.0
    else:
        trips_df["traffic_level"] = 0.35
        trips_df["weather"] = 1.0

    trips_df["traffic_level"] = pd.to_numeric(trips_df["traffic_level"], errors="coerce").fillna(0.35)
    trips_df["weather"] = pd.to_numeric(trips_df["weather"], errors="coerce").fillna(1.0)

    fare = pd.to_numeric(trips_df.get("fare", 0), errors="coerce").fillna(0)
    actual_fare = pd.to_numeric(trips_df.get("actual_fare", fare), errors="coerce").fillna(fare)
    baseline = np.maximum(1.0, fare)
    trips_df["surge_multiplier"] = (actual_fare / baseline).clip(lower=1.0, upper=3.0)

    output_cols = [
        "id",
        "driver_id",
        "pickup_lat",
        "pickup_lng",
        "dropoff_lat",
        "dropoff_lng",
        "request_time",
        "driver_assigned_time",
        "pickup_time",
        "dropoff_time",
        "ride_duration",
        "ride_distance",
        "ride_status",
        "distance",
        "estimated_time",
        "demand_density",
        "driver_density",
        "traffic_level",
        "time_of_day",
        "day_of_week",
        "weather",
        "surge_multiplier",
        "zone_key",
    ]

    dataset = trips_df[output_cols].copy()
    dataset = dataset.dropna(subset=["pickup_lat", "pickup_lng", "dropoff_lat", "dropoff_lng"])

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output, index=False)

    conn.close()
    return dataset
