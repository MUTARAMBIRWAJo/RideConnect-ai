"""Train custom ETA weighted regression model."""

from __future__ import annotations

import random
from typing import List

from algorithms.pricing.regression_model import LinearRegressionGD, train_test_split
from models.eta_model import ETAModel
from utils.datasets import load_csv_rows
from utils.logger import get_logger

logger = get_logger("train_eta")


def _synthetic_rows(n: int = 700):
    rows = []
    for _ in range(n):
        distance = random.uniform(0.8, 22.0)
        traffic = random.uniform(0.2, 1.0)
        hour = random.randint(0, 23)
        speed = random.uniform(18.0, 42.0)
        duration = (distance / speed) * 60.0 * (1.0 + 0.45 * traffic)
        rows.append({
            "distance_km": distance,
            "traffic_level": traffic,
            "time_of_day": hour,
            "road_speed_kmh": speed,
            "duration": duration,
        })
    return rows


def _build_dataset() -> tuple[List[List[float]], List[float]]:
    rows = load_csv_rows("datasets/eta_history.csv")
    if not rows:
        rows = _synthetic_rows()

    X, y = [], []
    for r in rows:
        distance = float(r["distance_km"])
        traffic = float(r.get("traffic_level", 0.5))
        hour = float(r.get("time_of_day", 12))
        speed = float(r.get("road_speed_kmh", 28.0))
        duration = float(r.get("duration", 0.0))
        if duration <= 0:
            duration = (distance / max(speed, 8.0)) * 60.0 * (1.0 + 0.45 * traffic)
        X.append([distance, traffic, hour, speed])
        y.append(duration)
    return X, y


def main() -> None:
    X, y = _build_dataset()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_ratio=0.2)

    linear = LinearRegressionGD(learning_rate=0.0009, epochs=1500)
    linear.fit(X_train, y_train)
    mae = linear.evaluate_mae(X_test, y_test) if X_test else linear.evaluate_mae(X_train, y_train)

    wrapper = ETAModel()
    wrapper.linear = linear
    wrapper.default_speed_kmh = 28.0
    path = wrapper.save()

    logger.info("ETA model trained | samples=%d | mae=%.4f | saved=%s", len(X), mae, path)


if __name__ == "__main__":
    main()
