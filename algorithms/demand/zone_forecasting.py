"""Zone-level demand and supply forecasting."""

from __future__ import annotations

from typing import Dict, List

from algorithms.demand.time_series_model import TimeSeriesForecaster


def forecast_zone_demand(zone_series: Dict[str, List[float]]) -> Dict[str, Dict[str, float]]:
    model = TimeSeriesForecaster()
    output: Dict[str, Dict[str, float]] = {}

    for zone, series in zone_series.items():
        pred_requests = max(0.0, model.forecast(series))
        driver_supply_needed = pred_requests * 0.72
        output[zone] = {
            "predicted_requests_per_zone": round(pred_requests, 2),
            "predicted_driver_supply_needed": round(driver_supply_needed, 2),
        }
    return output
