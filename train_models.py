"""Dependency-light model training pipeline for RideConnect.

Produces required artifacts:
- models/driver_matching.pkl
- models/eta_prediction.pkl
- models/demand_prediction.pkl
- models/surge_model.pkl

When DB access packages are unavailable, it trains from local dataset CSV or
synthetic bootstrap data so the service can still boot and serve predictions.
"""

from __future__ import annotations

import csv
import json
import math
import os
import pickle
import random
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

DATASET_PATH = Path("datasets/rides_dataset.csv")
RAW_KIGALI_DATASET_PATH = Path("docs/kigali_rides.csv")
ALLOW_RAW_KIGALI_FALLBACK = os.getenv("ALLOW_RAW_KIGALI_FALLBACK", "false").lower() == "true"
MODEL_DIR = Path("models")
METRICS_PATH = MODEL_DIR / "model_metrics.json"


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(max(a, 0.0)))


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def _load_rows_from_csv() -> list[dict[str, Any]]:
    if not DATASET_PATH.exists():
        if ALLOW_RAW_KIGALI_FALLBACK:
            return _load_rows_from_raw_kigali_csv()
        return []

    with DATASET_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _extract_driver_id(value: Any) -> int:
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else 0


def _load_rows_from_raw_kigali_csv() -> list[dict[str, Any]]:
    if not RAW_KIGALI_DATASET_PATH.exists():
        return []

    with RAW_KIGALI_DATASET_PATH.open("r", encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))

    if not raw_rows:
        return []

    zone_hour_counts: dict[tuple[str, int], int] = defaultdict(int)
    for r in raw_rows:
        dt_text = str(r.get("request_time", "")).strip()
        try:
            dt = datetime.strptime(dt_text, "%d/%m/%Y %H:%M")
            hour = dt.hour
        except Exception:
            hour = 12
        zone = f"{round(_safe_float(r.get('pickup_lat')), 2)}:{round(_safe_float(r.get('pickup_lng')), 2)}"
        zone_hour_counts[(zone, hour)] += 1

    rows: list[dict[str, Any]] = []
    for r in raw_rows:
        dt_text = str(r.get("request_time", "")).strip()
        try:
            dt = datetime.strptime(dt_text, "%d/%m/%Y %H:%M")
            hour = dt.hour
            dow = dt.weekday()
        except Exception:
            hour = 12
            dow = 0

        p_lat = _safe_float(r.get("pickup_lat"))
        p_lng = _safe_float(r.get("pickup_lng"))
        d_lat = _safe_float(r.get("dropoff_lat"))
        d_lng = _safe_float(r.get("dropoff_lng"))
        zone = f"{round(p_lat, 2)}:{round(p_lng, 2)}"

        distance = _safe_float(r.get("distance_km"))
        duration_min = _safe_float(r.get("duration_min"), max(1.0, distance / 28.0 * 60.0))
        surge = max(1.0, min(3.0, _safe_float(r.get("surge_multiplier"), 1.0)))

        if 7 <= hour <= 9 or 17 <= hour <= 19:
            traffic = 0.65
        elif 20 <= hour <= 23:
            traffic = 0.5
        else:
            traffic = 0.3

        rows.append(
            {
                "driver_id": str(_extract_driver_id(r.get("driver_id"))),
                "pickup_lat": str(p_lat),
                "pickup_lng": str(p_lng),
                "dropoff_lat": str(d_lat),
                "dropoff_lng": str(d_lng),
                "distance": str(distance),
                "estimated_time": str(duration_min),
                "demand_density": str(float(zone_hour_counts.get((zone, hour), 1))),
                "driver_density": "1.0",
                "traffic_level": str(traffic),
                "time_of_day": str(hour),
                "day_of_week": str(dow),
                "ride_duration": str(duration_min * 60.0),
                "surge_multiplier": str(surge),
            }
        )
    return rows


def _generate_synthetic_rows(n: int = 1200) -> list[dict[str, Any]]:
    rng = random.Random(2026)
    rows: list[dict[str, Any]] = []

    for _ in range(n):
        p_lat = -1.97 + rng.random() * 0.08
        p_lng = 30.02 + rng.random() * 0.10
        d_lat = -1.97 + rng.random() * 0.08
        d_lng = 30.02 + rng.random() * 0.10

        distance = _haversine_km(p_lat, p_lng, d_lat, d_lng)
        traffic = 0.2 + rng.random() * 0.7
        hour = rng.randint(0, 23)
        dow = rng.randint(0, 6)
        demand = max(1.0, (1.8 if 7 <= hour <= 9 or 17 <= hour <= 20 else 1.0) * (0.9 + rng.random() * 1.6))
        drivers = max(1.0, 0.8 + rng.random() * 3.0)
        eta_min = max(3.0, (distance / max(8.0, 28.0 * (1.05 - 0.5 * traffic))) * 60.0 + rng.random() * 4.0)
        surge = max(1.0, min(3.0, 1.0 + (demand / drivers - 1.0) * 0.35 + traffic * 0.15))

        rows.append(
            {
                "driver_id": str(rng.randint(1, 400)),
                "pickup_lat": f"{p_lat:.7f}",
                "pickup_lng": f"{p_lng:.7f}",
                "dropoff_lat": f"{d_lat:.7f}",
                "dropoff_lng": f"{d_lng:.7f}",
                "distance": f"{distance:.3f}",
                "estimated_time": f"{eta_min:.2f}",
                "demand_density": f"{demand:.3f}",
                "driver_density": f"{drivers:.3f}",
                "traffic_level": f"{traffic:.3f}",
                "time_of_day": str(hour),
                "day_of_week": str(dow),
                "ride_duration": f"{eta_min * 60:.2f}",
                "surge_multiplier": f"{surge:.3f}",
            }
        )

    return rows


def _load_training_rows() -> list[dict[str, Any]]:
    rows = _load_rows_from_csv()
    if rows:
        return rows
    return _generate_synthetic_rows()


def _train_matching(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], float]:
    by_driver: dict[int, tuple[float, float, int]] = {}

    for r in rows:
        driver_id = _safe_int(r.get("driver_id"), 0)
        if driver_id <= 0:
            continue

        lat = _safe_float(r.get("pickup_lat"))
        lng = _safe_float(r.get("pickup_lng"))

        if driver_id not in by_driver:
            by_driver[driver_id] = (lat, lng, 1)
        else:
            clat, clng, c = by_driver[driver_id]
            by_driver[driver_id] = ((clat * c + lat) / (c + 1), (clng * c + lng) / (c + 1), c + 1)

    drivers = [{"driver_id": did, "lat": lat, "lng": lng} for did, (lat, lng, _) in by_driver.items()]

    # Pseudo-accuracy: assign nearest centroid and compare to recorded driver_id when possible.
    checks = 0
    correct = 0
    for r in rows[:1500]:
        actual = _safe_int(r.get("driver_id"), 0)
        p_lat = _safe_float(r.get("pickup_lat"))
        p_lng = _safe_float(r.get("pickup_lng"))
        if actual <= 0 or not drivers:
            continue
        best = min(drivers, key=lambda d: _haversine_km(p_lat, p_lng, d["lat"], d["lng"]))
        checks += 1
        if _safe_int(best["driver_id"], -1) == actual:
            correct += 1

    accuracy = (correct / checks) if checks > 0 else 0.0
    return {"drivers": drivers}, float(accuracy)


def _train_eta(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], float]:
    speed_samples = []
    abs_errors = []

    for r in rows:
        dist = _safe_float(r.get("distance"), _haversine_km(
            _safe_float(r.get("pickup_lat")),
            _safe_float(r.get("pickup_lng")),
            _safe_float(r.get("dropoff_lat")),
            _safe_float(r.get("dropoff_lng")),
        ))
        duration_sec = _safe_float(r.get("ride_duration"), _safe_float(r.get("estimated_time")) * 60.0)
        if dist > 0 and duration_sec > 0:
            speed_samples.append(dist / (duration_sec / 3600.0))

    base_speed = max(8.0, min(60.0, mean(speed_samples) if speed_samples else 28.0))

    for r in rows[:2000]:
        dist = _safe_float(r.get("distance"), 0.0)
        traffic = _safe_float(r.get("traffic_level"), 0.35)
        predicted_min = (dist / max(8.0, base_speed * (1.05 - 0.55 * traffic))) * 60.0
        actual_min = _safe_float(r.get("ride_duration"), _safe_float(r.get("estimated_time")) * 60.0) / 60.0
        if actual_min > 0:
            abs_errors.append(abs(predicted_min - actual_min))

    mae = mean(abs_errors) if abs_errors else 0.0
    return {"base_speed_kmh": base_speed}, float(mae)


def _train_demand(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], float]:
    buckets: dict[tuple[str, int, int], list[float]] = defaultdict(list)

    for r in rows:
        zone = f"{round(_safe_float(r.get('pickup_lat')), 2)}:{round(_safe_float(r.get('pickup_lng')), 2)}"
        hour = _safe_int(r.get("time_of_day"), 12)
        dow = _safe_int(r.get("day_of_week"), 0)
        demand = _safe_float(r.get("demand_density"), 1.0)
        buckets[(zone, hour, dow)].append(demand)

    profile = {f"{z}|{h}|{d}": mean(vals) for (z, h, d), vals in buckets.items()}

    sq_err = []
    for r in rows[:2000]:
        zone = f"{round(_safe_float(r.get('pickup_lat')), 2)}:{round(_safe_float(r.get('pickup_lng')), 2)}"
        hour = _safe_int(r.get("time_of_day"), 12)
        dow = _safe_int(r.get("day_of_week"), 0)
        actual = _safe_float(r.get("demand_density"), 1.0)
        pred = _safe_float(profile.get(f"{zone}|{hour}|{dow}", 1.0), 1.0)
        sq_err.append((pred - actual) ** 2)

    rmse = math.sqrt(mean(sq_err)) if sq_err else 0.0
    return {"profile": profile, "default": 1.0}, float(rmse)


def _train_surge(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], float]:
    errs = []

    for r in rows[:3000]:
        demand = max(0.1, _safe_float(r.get("demand_density"), 1.0))
        supply = max(0.1, _safe_float(r.get("driver_density"), 1.0))
        traffic = _safe_float(r.get("traffic_level"), 0.35)
        ratio = demand / supply
        pred = max(1.0, min(3.0, 1.0 + max(0.0, ratio - 1.0) * 0.35 + traffic * 0.15))
        actual = max(1.0, min(3.0, _safe_float(r.get("surge_multiplier"), 1.0)))
        errs.append(abs(pred - actual))

    mae = mean(errs) if errs else 0.0
    return {"ratio_weight": 0.35, "traffic_weight": 0.15}, float(mae)


def _save_pickle(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(payload, f)


def run_training_pipeline() -> dict[str, Any]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    rows = _load_training_rows()

    matching_model, matching_acc = _train_matching(rows)
    eta_model, eta_mae = _train_eta(rows)
    demand_model, demand_rmse = _train_demand(rows)
    surge_model, surge_mae = _train_surge(rows)

    _save_pickle(MODEL_DIR / "driver_matching.pkl", matching_model)
    _save_pickle(MODEL_DIR / "eta_prediction.pkl", eta_model)
    _save_pickle(MODEL_DIR / "demand_prediction.pkl", demand_model)
    _save_pickle(MODEL_DIR / "surge_model.pkl", surge_model)

    results = {
        "dataset_rows": len(rows),
        "matching_accuracy": round(float(matching_acc), 6),
        "eta_mae_minutes": round(float(eta_mae), 6),
        "demand_rmse": round(float(demand_rmse), 6),
        "surge_mae": round(float(surge_mae), 6),
        "model_paths": {
            "driver_matching": str(MODEL_DIR / "driver_matching.pkl"),
            "eta_prediction": str(MODEL_DIR / "eta_prediction.pkl"),
            "demand_prediction": str(MODEL_DIR / "demand_prediction.pkl"),
            "surge_model": str(MODEL_DIR / "surge_model.pkl"),
        },
    }

    with METRICS_PATH.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    print(json.dumps(run_training_pipeline(), indent=2))
