"""Utilities for saving/loading model weights."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from utils.config import settings


def ensure_weights_dir() -> str:
    os.makedirs(settings.model_weights_dir, exist_ok=True)
    return settings.model_weights_dir


def save_json_weights(file_name: str, payload: Dict[str, Any]) -> str:
    base = ensure_weights_dir()
    path = os.path.join(base, file_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def load_json_weights(file_name: str, default: Dict[str, Any]) -> Dict[str, Any]:
    base = ensure_weights_dir()
    path = os.path.join(base, file_name)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
