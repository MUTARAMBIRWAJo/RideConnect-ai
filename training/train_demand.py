"""Train custom demand forecasting model state."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Dict, List

from models.demand_model import DemandModel
from utils.datasets import load_csv_rows
from utils.logger import get_logger

logger = get_logger("train_demand")


def _synthetic_zone_data() -> Dict[str, List[float]]:
    zone_hist: Dict[str, List[float]] = defaultdict(list)
    zones = ["kigali_core", "airport", "kimironko", "nyamirambo", "remera"]
    for z in zones:
        base = random.uniform(8.0, 22.0)
        for i in range(96):
            hour = i % 24
            peak = 1.35 if (7 <= hour <= 9 or 17 <= hour <= 20) else 0.9
            zone_hist[z].append(base * peak + random.uniform(-1.5, 1.5))
    return zone_hist


def _load_zone_data() -> Dict[str, List[float]]:
    rows = load_csv_rows("datasets/demand_history.csv")
    if not rows:
        return _synthetic_zone_data()

    zone_hist: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        zone_hist[r["zone"]].append(float(r["requests"]))
    return zone_hist


def main() -> None:
    zone_hist = _load_zone_data()
    model = DemandModel()

    for zone, values in zone_hist.items():
        for v in values:
            model.update_observation(zone, v)

    path = model.save()
    logger.info("Demand model trained | zones=%d | saved=%s", len(zone_hist), path)


if __name__ == "__main__":
    main()
