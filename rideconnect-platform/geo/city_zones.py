"""City configuration and zone helpers for multi-city routing and demand."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import yaml

CONFIG_ROOT = Path(__file__).resolve().parents[1] / "configs" / "city_configs"


def load_city_config(city_id: str) -> Dict:
    path = CONFIG_ROOT / f"{city_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Missing city config: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def list_city_zones(city_id: str) -> List[Dict]:
    cfg = load_city_config(city_id)
    return list(cfg.get("city_zones", []))


def resolve_zone(city_id: str, lat: float, lng: float) -> str:
    zones = list_city_zones(city_id)
    if not zones:
        return "unknown"
    best = min(
        zones,
        key=lambda z: abs(float(z["center_lat"]) - lat) + abs(float(z["center_lng"]) - lng),
    )
    return str(best.get("zone_id", "unknown"))
