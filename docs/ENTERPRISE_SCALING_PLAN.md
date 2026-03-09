# Enterprise Scaling Plan (RideConnect)

## Target Throughput
- 10,000+ active drivers
- 5,000+ concurrent ride requests
- sub-second dispatch path under normal load

## Design Decisions Implemented
- Event streaming decouples write path from analytics/model updates:
  - topics: `ride_requests`, `driver_locations`, `ride_status`, `demand_metrics`
- Stateless service decomposition for horizontal scale:
  - gateway + dispatch/pricing/eta/demand/driver-prediction services
- O(1) zone lookup and grid-based candidate narrowing:
  - `geo/spatial_index.py`
- Graph-based routing with algorithm selection:
  - Dijkstra and A* under `routing/`
- Online learning loop for continuous adaptation:
  - `online_learning/incremental_training.py`
  - `online_learning/model_updater.py`
- Multi-city parameter isolation by config:
  - `configs/city_configs/*.yaml`

## Runtime Strategy
- Scale `dispatch-service`, `eta-service`, and `pricing-service` replicas first.
- Increase Kafka partitions for `ride_requests` and `driver_locations` topics.
- Keep event processors isolated from request-serving services.

## Fault Tolerance
- Kafka producer/consumer wrappers include memory fallback for local/dev continuity.
- Service failures are isolated behind gateway orchestration boundaries.
