# RideConnect AI Repository Audit

## Scope
Audit date: 2026-03-09
Repository: `ai-service`

## Existing Components (Before This Upgrade)

### Existing AI Models
- `app/model.py`: price prediction wrapper using persisted model + heuristic fallback.
- `app/matching_engine.py`: weighted scoring model for driver-passenger matching.
- `app/eta_predictor.py`: ETA model (Gradient Boosting + heuristic fallback).
- `app/demand_prediction.py`: demand prediction (RF + optional LSTM wrapper).
- `app/hotspot_detection.py`: K-Means clustering for demand hotspots.
- `app/anomaly_detection.py`: IsolationForest for fare anomaly detection.
- `app/behavior_analysis.py`: driver behavior classification model.

### Existing Algorithms
- Haversine distance calculations.
- Weighted multi-factor ranking for matching.
- K-Means clustering for hotspots.
- Random Forest and Gradient Boosting pipelines.
- IsolationForest anomaly detection.

### Existing API Endpoints
- Health: `/`, `/health`
- Predictions: `/predict-price`, `/predict-driver`
- Advanced AI: `/match-driver`, `/predict-demand`, `/demand-hotspots`, `/optimize-route`, `/estimate-arrival`, `/analyze-driver`, `/detect-fare-anomaly`
- Tracking: `/update-driver-location`, `/nearby-drivers`
- Analytics/Admin: `/analytics/*`, `/retrain`, `/jobs/{job_id}`

### Existing Training Scripts
- `app/train_model.py`, `app/train.py`, `app/retraining.py`
- `train_demand_model.py`

### Existing Deployment
- Root `Dockerfile`, `docker-compose.yml`, `render.yaml`
- Redis integration for caching and queueing via `app/service.py`

### Existing Dataset / Storage Structure
- SQL migrations and seed files under `migrations/` and `seeds/`
- Model artifact directory at `models/`
- No standardized CSV dataset directory for model training workflows.

## Missing Components Identified

### Architecture Gaps
- Missing modular standalone architecture requested under `api/`, `algorithms/`, `training/`, `utils/`, `docker/`.
- Missing dedicated API server entrypoint at `api/server.py`.

### Model / Algorithm Gaps
- No explicit from-scratch linear regression module for pricing.
- No explicit custom weighted ETA regression module separated from app internals.
- No standalone time-series + smoothing demand module by zone.
- No dedicated assignment optimizer module with fairness balancing abstraction.

### Training Pipeline Gaps
- Missing standardized script set:
  - `training/train_matching.py`
  - `training/train_pricing.py`
  - `training/train_eta.py`
  - `training/train_demand.py`
- Missing unified model-weight persistence under `models/weights/`.

### API Contract Gaps
- Missing required standalone endpoints:
  - `POST /ai/match-driver`
  - `POST /ai/predict-price`
  - `POST /ai/predict-eta`
  - `POST /ai/forecast-demand`

### Deployment Gaps
- Missing requested Dockerfile in `docker/Dockerfile` with `uvicorn api.server:app --host 0.0.0.0 --port 8000`.

## Upgrades Implemented in This Change

### New Standalone Architecture Added
- `api/` with route modules and `api/server.py`
- `algorithms/` with matching, pricing, eta, demand submodules
- `training/` scripts for all four required AI capabilities
- `utils/` for config, logging, storage, dataset loading
- `docker/Dockerfile` for independent microservice runtime
- `models/weights/` for persisted custom model weights
- `datasets/` + documentation for expected input CSV formats

### Compliance Notes
- No external AI APIs used.
- No OpenAI/HuggingFace/proprietary AI service dependency introduced.
- All new AI logic is custom algorithmic code in-repo.
