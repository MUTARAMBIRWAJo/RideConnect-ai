"""Train custom pricing model with linear regression + surge components."""

from __future__ import annotations

from typing import List

from algorithms.pricing.regression_model import LinearRegressionGD, train_test_split
from models.pricing_model import PricingModel
from utils.datasets import load_csv_rows, synthetic_trip_rows
from utils.logger import get_logger

logger = get_logger("train_pricing")


def _build_dataset() -> tuple[List[List[float]], List[float]]:
    rows = load_csv_rows("datasets/pricing_history.csv")
    if not rows:
        rows = synthetic_trip_rows(700)

    X: List[List[float]] = []
    y: List[float] = []
    for r in rows:
        distance = float(r["distance"])
        duration = float(r["duration"])
        demand = float(r.get("demand_level", 0.5))
        traffic = float(r.get("traffic_level", 0.5))
        tod = float(r.get("time_of_day", 12))
        fare = float(r.get("fare", 0.0))
        if fare <= 0:
            fare = 2.0 + 0.62 * distance + 0.14 * duration + 1.4 * demand
        X.append([distance, duration, demand, traffic, tod])
        y.append(fare)
    return X, y


def main() -> None:
    X, y = _build_dataset()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_ratio=0.2)

    model = LinearRegressionGD(learning_rate=0.0008, epochs=1800)
    model.fit(X_train, y_train)
    mae = model.evaluate_mae(X_test, y_test) if X_test else model.evaluate_mae(X_train, y_train)

    wrapper = PricingModel()
    wrapper.linear = model
    wrapper.base_fare = 2.0
    wrapper.distance_rate = 0.62
    wrapper.time_rate = 0.14
    path = wrapper.save()

    logger.info("Pricing model trained | samples=%d | mae=%.4f | saved=%s", len(X), mae, path)


if __name__ == "__main__":
    main()
