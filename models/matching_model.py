"""Inference wrapper for driver-passenger matching."""

from __future__ import annotations

from typing import Dict, List

from algorithms.matching.assignment_optimizer import optimize_assignment
from utils.storage import load_json_weights, save_json_weights


class MatchingModel:
    def __init__(self) -> None:
        self.fairness_state: Dict[int, int] = {}
        self.weights = load_json_weights(
            "matching_weights.json",
            {
                "distance_weight": 0.35,
                "rating_weight": 0.25,
                "availability_weight": 0.20,
                "pickup_time_weight": 0.20,
            },
        )

    def predict_best_driver(self, passenger: Dict, drivers: List[Dict]) -> Dict:
        best = optimize_assignment(passenger, drivers, self.fairness_state)
        if best:
            did = int(best["driver_id"])
            self.fairness_state[did] = self.fairness_state.get(did, 0) + 1
        return best

    def save(self) -> str:
        return save_json_weights("matching_weights.json", self.weights)
