"""Time-series demand forecasting with moving average and exponential smoothing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class TimeSeriesForecaster:
    alpha: float = 0.35
    moving_window: int = 5

    def moving_average(self, values: List[float]) -> float:
        if not values:
            return 0.0
        window = values[-self.moving_window :]
        return sum(window) / len(window)

    def exponential_smoothing(self, values: List[float]) -> float:
        if not values:
            return 0.0
        smoothed = values[0]
        for v in values[1:]:
            smoothed = self.alpha * v + (1.0 - self.alpha) * smoothed
        return smoothed

    def forecast(self, values: List[float]) -> float:
        ma = self.moving_average(values)
        es = self.exponential_smoothing(values)
        return 0.45 * ma + 0.55 * es
