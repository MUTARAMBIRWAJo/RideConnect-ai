"""Dataset loading and basic synthetic fallbacks."""

from __future__ import annotations

import csv
import os
import random
from typing import Dict, List


def load_csv_rows(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader]


def synthetic_trip_rows(n: int = 300) -> List[Dict[str, float]]:
    rows = []
    for _ in range(n):
        distance = random.uniform(1.0, 20.0)
        duration = distance * random.uniform(2.0, 4.5)
        demand = random.uniform(0.2, 1.0)
        traffic = random.uniform(0.2, 1.0)
        hour = random.randint(0, 23)
        rows.append(
            {
                "distance": distance,
                "duration": duration,
                "demand_level": demand,
                "traffic_level": traffic,
                "time_of_day": hour,
                "city_zone": random.choice(["A", "B", "C", "D"]),
            }
        )
    return rows
