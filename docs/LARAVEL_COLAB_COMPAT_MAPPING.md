# Laravel To Colab Compatibility Mapping

This mapping is based on currently used legacy endpoints in this repo:
- `/predict-price`
- `/predict-driver`
- `/predict-demand`

The API now supports zero-change migration by keeping old routes and internally translating payloads to Colab-compatible schemas.

## 1) Legacy Pricing

Legacy request (unchanged):
```json
{
  "distance_km": 6.5,
  "demand_level": 4,
  "traffic_level": 3,
  "ride_type": "standard"
}
```

RURA-aware fields you can now add (optional but recommended):
```json
{
  "route_code": "101",
  "corridor": "A",
  "origin_stop": "REMERA BUS PARK",
  "destination_stop": "DOWN TOWN BUS PARK"
}
```

Pricing priority now:
1. Official RURA fare by `route_code`
2. Official RURA fare by `origin_stop` + `destination_stop` (+ optional `corridor`)
3. Corridor anchored prediction if `corridor` is provided
4. Existing model prediction fallback

Laravel endpoint to call (no controller changes):
- `POST /predict-price`

Translator route (explicit compatibility):
- `POST /compat/predict-price`

Internal Colab translation:
- `demand_level` int (1-5) -> label (`low`/`medium`/`high`)
- `traffic_level` -> `wait_time_min` and rush-hour signal
- current server time -> `hour`, `weekday`, `month`, `is_weekend`
- `pickup_zone` default -> `CBD` (legacy price payload has no coordinates)

Response shape (legacy-compatible):
- `recommended_price`
- `currency`
- `model_used`
- `cached`

Additional response metadata when available:
- `fare_source` (`rura_official`, `corridor_blend`, or model-based)
- `route_code`, `corridor`, `origin_stop`, `destination_stop` (for official fare matches)

Extra debug fields returned:
- `translated_colab_request`
- `colab_response`

## 2) Legacy Driver Selection

Legacy request (unchanged):
```json
{
  "pickup_lat": -1.9441,
  "pickup_lng": 30.0619,
  "ride_type": "standard"
}
```

Laravel endpoint to call (no controller changes):
- `POST /predict-driver`

Translator route (explicit compatibility):
- `POST /compat/predict-driver`

Internal behavior:
- Uses `models/driver_matching.pkl` nearest-driver index for deterministic best driver.
- Translates to Colab matching schema for compatibility scoring enrichment.

Response shape (legacy-compatible):
- `driver_id`
- `driver_name`
- `rating`
- `total_rides`
- `note`

Extra debug fields returned:
- `translated_colab_request`
- `colab_response`

## 3) Legacy Demand

Legacy-compatible translator endpoint:
- `POST /compat/predict-demand`

Current merged behavior:
- Existing `POST /predict-demand` in app layer can use Colab compatibility path.
- In API layer, `POST /predict/demand` is native Colab schema and `POST /compat/predict-demand` translates legacy payload.

## Endpoint Summary

Use these for zero-change Laravel migration:
- `POST /predict-price`
- `POST /predict-driver`
- `POST /compat/predict-demand`

Use these for native Colab schema:
- `POST /predict/demand`
- `POST /predict/match`
- `POST /predict/behavior`
- `POST /predict/surge`
- `GET /models/info`

## Notes

- Authentication remains `X-API-Key`.
- Supabase remains the primary runtime data source.
- CSV artifacts are retained for model bootstrapping/history only, not primary production reads.
