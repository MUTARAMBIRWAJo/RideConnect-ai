"""Train custom matching weight profile from historical assignment behavior."""

from __future__ import annotations

from typing import Dict, List

from models.matching_model import MatchingModel
from utils.datasets import load_csv_rows
from utils.logger import get_logger
from utils.storage import save_json_weights

logger = get_logger("train_matching")


def _default_weights() -> Dict[str, float]:
    return {
        "distance_weight": 0.35,
        "rating_weight": 0.25,
        "availability_weight": 0.20,
        "pickup_time_weight": 0.20,
    }


def _learn_weights(rows: List[Dict[str, str]]) -> Dict[str, float]:
    if not rows:
        return _default_weights()

    selected = [r for r in rows if str(r.get("selected", "1")) == "1"]
    if not selected:
        return _default_weights()

    avg_distance = sum(float(r.get("distance_km", 2.0)) for r in selected) / len(selected)
    avg_rating = sum(float(r.get("driver_rating", 4.0)) for r in selected) / len(selected)
    avg_eta = sum(float(r.get("eta_pickup_minutes", 8.0)) for r in selected) / len(selected)

    # Convert historical tendencies into normalized score weights.
    distance_weight = max(0.2, min(0.5, 1.0 / max(avg_distance, 1.0)))
    rating_weight = max(0.15, min(0.4, avg_rating / 10.0))
    pickup_weight = max(0.15, min(0.35, 1.0 / max(avg_eta, 2.0)))
    availability_weight = max(0.1, 1.0 - (distance_weight + rating_weight + pickup_weight))

    total = distance_weight + rating_weight + pickup_weight + availability_weight
    return {
        "distance_weight": round(distance_weight / total, 4),
        "rating_weight": round(rating_weight / total, 4),
        "availability_weight": round(availability_weight / total, 4),
        "pickup_time_weight": round(pickup_weight / total, 4),
    }


def main() -> None:
    rows = load_csv_rows("datasets/matching_history.csv")
    weights = _learn_weights(rows)
    path = save_json_weights("matching_weights.json", weights)

    model = MatchingModel()
    model.weights = weights
    model.save()

    logger.info("Matching model trained | samples=%d | saved=%s", len(rows), path)


if __name__ == "__main__":
    main()
