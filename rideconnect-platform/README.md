# RideConnect Enterprise Platform

Enterprise-grade real-time ride-hailing intelligence platform.

## Capabilities
- Kafka-compatible real-time ride event streaming
- Driver movement prediction (Markov/probabilistic)
- Graph-based routing (Dijkstra + A*)
- Online learning (incremental model updates)
- Multi-city configs (Kigali, Nairobi, Lagos)
- Microservice architecture with API gateway

## Architecture
- `gateway/api_gateway.py`
- `services/dispatch-service/`
- `services/pricing-service/`
- `services/eta-service/`
- `services/demand-service/`
- `services/driver-prediction-service/`
- `streaming/` (producer, consumer, event processors)
- `routing/` (graph builder + shortest-path engine)
- `prediction/` (driver movement + demand)
- `online_learning/` (incremental training + model updater)
- `geo/` (spatial index + city zones)
- `configs/city_configs/`
- `docker/docker-compose.enterprise.yml`

## Kafka Topics
- `ride_requests`
- `driver_locations`
- `ride_status`
- `demand_metrics`

## Event Types
- `driver_location_updates`
- `ride_requested`
- `ride_assigned`
- `ride_started`
- `ride_completed`
- `ride_cancelled`

## Bounded-Latency Gateway Behavior
- Gateway uses per-service timeout budgets:
	- `DISPATCH_TIMEOUT_MS`
	- `ETA_TIMEOUT_MS`
	- `PRICING_TIMEOUT_MS`
- `POST /v1/rides/request` always returns a usable response and includes:
	- `partial_response` (`true|false`)
	- `degraded_services` (list of timed-out/unavailable dependencies)
- Gateway supports Redis-backed shared cache/coalescing for cross-worker coordination
	(fallbacks to process-local mode when Redis is unavailable).

## Run (Dev)
From repository root:

```bash
cd rideconnect-platform/docker
docker compose -f docker-compose.enterprise.yml up --build
```

Gateway will be available on `http://localhost:8100`.
