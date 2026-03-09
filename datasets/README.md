# Datasets

Place your training datasets in this folder.

Supported CSV files:
- `pricing_history.csv`: `distance,duration,demand_level,traffic_level,time_of_day,city_zone,fare`
- `eta_history.csv`: `distance_km,traffic_level,time_of_day,road_speed_kmh,duration`
- `demand_history.csv`: `zone,requests`
- `matching_history.csv`: `distance_km,driver_rating,eta_pickup_minutes,selected`

The training scripts automatically fall back to synthetic data if these files are absent.
