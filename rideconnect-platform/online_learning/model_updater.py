"""Model updater and weight refresh storage for online learning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from online_learning.incremental_training import IncrementalTrainer

WEIGHTS_PATH = Path(__file__).resolve().parents[1] / "configs" / "online_weights.json"


def update_model_weights(trainer: IncrementalTrainer) -> Dict:
    payload = {
        "price_multiplier": dict(trainer.price_multiplier),
        "eta_bias_minutes": dict(trainer.eta_bias_minutes),
    }
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_model_weights() -> Dict:
    if not WEIGHTS_PATH.exists():
        return {"price_multiplier": {}, "eta_bias_minutes": {}}
    return json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
