"""Inference bridge for Colab-exported RideConnect model artifacts."""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import numpy.core as np_core
import numpy.core._multiarray_umath as np_core_multiarray_umath
import numpy.core.multiarray as np_core_multiarray
import numpy.core.numeric as np_core_numeric
import numpy.random._pickle as np_random_pickle

from utils.config import settings

try:
    from tensorflow.keras.models import load_model
except Exception:  # pragma: no cover - optional runtime dependency
    load_model = None


class ColabInferenceService:
    def __init__(self, models_dir: Path) -> None:
        self.models_dir = models_dir
        self._loaded = False

        self.demand_model: Any | None = None
        self.matching_model: Any | None = None
        self.behavior_model: Any | None = None
        self.surge_model: Any | None = None

        self.scaler_demand: Any | None = None
        self.le_zone: Any | None = None
        self.le_demand: Any | None = None
        self.le_period: Any | None = None
        self.zone_mapping: dict[str, int] = {}
        self.load_warnings: list[str] = []

    def _require_file(self, name: str) -> Path:
        path = self.models_dir / name
        if not path.exists():
            raise RuntimeError(
                f"Required Colab artifact missing: {path}. "
                "Expected files under docs/rideconnect_ai_service or COLAB_MODELS_DIR."
            )
        return path

    def _load_joblib(self, artifact: str) -> Any:
        path = self._require_file(artifact)
        return joblib.load(path)

    def _load_optional_joblib(self, artifact: str) -> Any | None:
        try:
            return self._load_joblib(artifact)
        except Exception as exc:
            self.load_warnings.append(f"{artifact}: {exc}")
            return None

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        try:
            if load_model is not None:
                try:
                    self.demand_model = load_model(str(self._require_file("demand_lstm.h5")))
                except Exception as exc:
                    self.load_warnings.append(f"demand_lstm.h5: {exc}")

            self.matching_model = self._load_optional_joblib("matching_rf.pkl")
            self.behavior_model = self._load_optional_joblib("behavior_gb.pkl")
            self.surge_model = self._load_optional_joblib("surge_xgb.pkl")

            self.scaler_demand = self._load_optional_joblib("scaler_demand.pkl")
            self.le_zone = self._load_optional_joblib("le_zone.pkl")
            self.le_demand = self._load_optional_joblib("le_demand.pkl")
            self.le_period = self._load_optional_joblib("le_period.pkl")

            with self._require_file("zone_mapping.json").open("r", encoding="utf-8") as f:
                raw_mapping = json.load(f)
            self.zone_mapping = {str(k): int(v) for k, v in raw_mapping.items()}
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed loading Colab model artifacts: {exc}") from exc

        self._loaded = True

    @staticmethod
    def _time_period(hour: int) -> str:
        if 7 <= hour <= 9:
            return "morning_rush"
        if 17 <= hour <= 19:
            return "evening_rush"
        if 20 <= hour <= 23:
            return "night"
        if 0 <= hour <= 5:
            return "late_night"
        return "off_peak"

    def _encode_zone(self, zone: str) -> int:
        if zone in self.zone_mapping:
            return int(self.zone_mapping[zone])
        return int(self.zone_mapping.get("Other", 0))

    def _encode_period(self, hour: int) -> int:
        period = self._time_period(hour)
        try:
            return int(self.le_period.transform([period])[0])
        except Exception:
            return 0

    def _encode_demand(self, demand_level: str) -> int:
        try:
            return int(self.le_demand.transform([demand_level])[0])
        except Exception:
            return 1

    def _demand_labels(self) -> list[str]:
        classes = getattr(self.le_demand, "classes_", None)
        if classes is None:
            return ["low", "medium", "high"]
        return [str(c) for c in classes]

    def predict_demand(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_loaded()

        hour = int(payload["hour"])
        zone_enc = self._encode_zone(str(payload["pickup_zone"]))
        period_enc = self._encode_period(hour)
        is_rush = 1 if (7 <= hour <= 9 or 17 <= hour <= 19) else 0

        x = np.array(
            [[
                hour,
                int(payload["weekday"]),
                int(payload["month"]),
                int(payload["is_weekend"]),
                is_rush,
                zone_enc,
                period_enc,
                int(payload.get("zone_hour_count", 5)),
            ]],
            dtype=float,
        )

        if self.demand_model is not None:
            x_scaled = self.scaler_demand.transform(x).reshape(1, 1, 8)
            probs = np.asarray(self.demand_model.predict(x_scaled, verbose=0)[0], dtype=float)
        else:
            rush_boost = 0.18 if is_rush else 0.0
            weekend_adjust = -0.08 if int(payload["is_weekend"]) else 0.04
            load_factor = min(1.0, max(0.0, int(payload.get("zone_hour_count", 5)) / 12.0))
            low = max(0.05, 0.52 - rush_boost - 0.35 * load_factor - weekend_adjust)
            high = max(0.05, 0.12 + rush_boost + 0.45 * load_factor + weekend_adjust)
            medium = max(0.05, 1.0 - low - high)
            total = low + medium + high
            probs = np.asarray([high, low, medium], dtype=float) / total

        pred_idx = int(np.argmax(probs))

        labels = self._demand_labels()
        pred_label = labels[pred_idx] if pred_idx < len(labels) else str(pred_idx)

        by_class = {}
        for i, p in enumerate(probs):
            label = labels[i] if i < len(labels) else str(i)
            by_class[label] = round(float(p), 3)

        return {
            "zone": str(payload["pickup_zone"]),
            "predicted_demand": pred_label,
            "confidence": round(float(np.max(probs)), 3),
            "probabilities": by_class,
        }

    def predict_match(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_loaded()

        x = [[
            int(payload["hour"]),
            int(payload["weekday"]),
            int(payload["is_weekend"]),
            int(payload["is_rush_hour"]),
            self._encode_zone(str(payload["pickup_zone"])),
            self._encode_zone(str(payload["dropoff_zone"])),
            float(payload["distance_km"]),
            float(payload["driver_rating"]),
            float(payload["driver_idle_time"]),
            float(payload["driver_cancel_rate"]),
            float(payload["driver_avg_rating"]),
            int(payload["driver_total_rides"]),
            float(payload["surge_multiplier"]),
            self._encode_demand(str(payload["demand_level"])),
        ]]
        if self.matching_model is not None:
            prob = float(self.matching_model.predict_proba(x)[0][1])
        else:
            rating = max(0.0, min(5.0, float(payload["driver_rating"]))) / 5.0
            cancel_penalty = max(0.0, min(1.0, float(payload["driver_cancel_rate"])))
            idle_factor = max(0.0, min(1.0, float(payload["driver_idle_time"]) / 30.0))
            surge_penalty = max(0.0, min(1.0, (float(payload["surge_multiplier"]) - 1.0) / 1.5))
            distance_penalty = max(0.0, min(1.0, float(payload["distance_km"]) / 25.0))
            raw = 0.68 * rating + 0.22 * idle_factor - 0.35 * cancel_penalty - 0.18 * surge_penalty - 0.12 * distance_penalty
            prob = max(0.05, min(0.95, raw))
        return {
            "completion_probability": round(prob, 3),
            "recommended": bool(prob >= 0.65),
        }

    def predict_behavior(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_loaded()

        x = [[
            int(payload["hour"]),
            int(payload["weekday"]),
            int(payload["is_rush_hour"]),
            float(payload["driver_rating"]),
            float(payload["driver_idle_time"]),
            int(payload["driver_total_rides"]),
            float(payload["driver_cancel_rate"]),
            float(payload["distance_km"]),
            float(payload["duration_min"]),
            float(payload["fare_rwf"]),
            float(payload["surge_multiplier"]),
            self._encode_zone(str(payload["pickup_zone"])),
        ]]

        if self.behavior_model is not None:
            is_risky = bool(self.behavior_model.predict(x)[0])
            risk_prob = float(self.behavior_model.predict_proba(x)[0][1])
        else:
            cancel_rate = max(0.0, min(1.0, float(payload["driver_cancel_rate"])))
            rating_penalty = max(0.0, (4.6 - float(payload["driver_rating"])) / 2.0)
            idle_penalty = max(0.0, min(1.0, float(payload["driver_idle_time"]) / 40.0))
            surge_penalty = max(0.0, min(1.0, (float(payload["surge_multiplier"]) - 1.0) / 1.5))
            risk_prob = max(0.02, min(0.98, 0.45 * cancel_rate + 0.28 * rating_penalty + 0.17 * idle_penalty + 0.1 * surge_penalty))
            is_risky = bool(risk_prob >= 0.5)
        if risk_prob > 0.7:
            level = "high"
        elif risk_prob > 0.4:
            level = "medium"
        else:
            level = "low"

        return {
            "risky_driver": is_risky,
            "risk_score": round(risk_prob, 3),
            "risk_level": level,
        }

    def predict_surge(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_loaded()

        x = [[
            int(payload["hour"]),
            int(payload["weekday"]),
            int(payload["is_weekend"]),
            int(payload["is_rush_hour"]),
            int(payload["month"]),
            self._encode_zone(str(payload["pickup_zone"])),
            float(payload["distance_km"]),
            int(payload.get("zone_hour_count", 5)),
            self._encode_demand(str(payload["demand_level"])),
            float(payload["driver_idle_time"]),
            float(payload["wait_time_min"]),
        ]]

        if self.surge_model is not None:
            multiplier = float(self.surge_model.predict(x)[0])
        else:
            rush_boost = 0.2 if int(payload["is_rush_hour"]) else 0.0
            demand_boost = 0.18 if str(payload["demand_level"]).lower() == "high" else 0.08
            wait_boost = min(0.35, float(payload["wait_time_min"]) / 30.0)
            idle_relief = min(0.2, float(payload["driver_idle_time"]) / 120.0)
            multiplier = 1.0 + rush_boost + demand_boost + wait_boost - idle_relief
        multiplier = round(max(1.0, min(2.5, multiplier)), 2)
        return {"surge_multiplier": multiplier}

    def model_info(self) -> dict[str, Any]:
        self._ensure_loaded()
        availability = {
            "demand_model": bool(self.demand_model is not None),
            "matching_model": bool(self.matching_model is not None),
            "behavior_model": bool(self.behavior_model is not None),
            "surge_model": bool(self.surge_model is not None),
        }
        log_path = self.models_dir / "retrain_log.json"
        if log_path.exists():
            with log_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            payload["model_availability"] = availability
            if self.load_warnings:
                payload["load_warnings"] = self.load_warnings
            return payload

        payload = {
            "message": "No retrain log yet. Run initial training first.",
            "model_availability": availability,
        }
        if self.load_warnings:
            payload["load_warnings"] = self.load_warnings
        return payload


@lru_cache(maxsize=1)
def get_colab_inference_service() -> ColabInferenceService:
    return ColabInferenceService(Path(settings.colab_models_dir))


_ORIGINAL_BITGEN_CTOR = getattr(np_random_pickle, "__bit_generator_ctor", None)
if _ORIGINAL_BITGEN_CTOR is not None:
    def _compat_bit_generator_ctor(bit_generator_name: Any):
        if isinstance(bit_generator_name, type):
            normalized = bit_generator_name.__name__
        else:
            text = str(bit_generator_name)
            if text.startswith("<class '") and text.endswith("'>"):
                text = text[8:-2]
            normalized = text.rsplit(".", 1)[-1] if "." in text else text
        return _ORIGINAL_BITGEN_CTOR(normalized)

    np_random_pickle.__bit_generator_ctor = _compat_bit_generator_ctor

# Older Colab/joblib artifacts may reference private NumPy module paths that differ
# across NumPy releases (e.g., numpy._core vs numpy.core).
sys.modules.setdefault("numpy._core", np_core)
sys.modules.setdefault("numpy._core.numeric", np_core_numeric)
sys.modules.setdefault("numpy._core.multiarray", np_core_multiarray)
sys.modules.setdefault("numpy._core._multiarray_umath", np_core_multiarray_umath)
