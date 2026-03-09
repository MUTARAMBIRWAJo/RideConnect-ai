"""Configuration values for the standalone AI microservice."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = "RideConnect AI"
    api_key: str = os.getenv("API_KEY", "")
    model_weights_dir: str = os.getenv("MODEL_WEIGHTS_DIR", "models/weights")
    default_zone: str = os.getenv("DEFAULT_ZONE", "kigali_core")


settings = Settings()
