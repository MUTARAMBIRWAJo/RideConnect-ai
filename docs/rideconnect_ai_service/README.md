# RideConnect AI Service

## Setup
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Notes:
- Use the root `requirements.txt` as the single dependency source.
- Runtime container dependencies are in `docker/requirements.standalone.txt`.

## Consolidation
- Standalone duplicate `main.py` in this docs folder was merged into `app/main.py` and removed.
- Use the single production entrypoint `app/main.py` for both compatibility and advanced routes.

## Model Artifacts
- Colab artifacts remain in this folder (`behavior_gb.pkl`, `demand_lstm.h5`, `le_zone.pkl`, `zone_mapping.json`).
- `le_zone.pkl` and `zone_mapping.json` are aligned and should be kept in sync with model retraining outputs.
- `demand_lstm.h5` is the single active demand model artifact used at runtime.

## Endpoints
- POST /predict/demand   → Demand level for a zone at a given time
- POST /predict/match    → Completion probability for a driver-passenger pair
- POST /predict/behavior → Driver risk assessment
- POST /predict/surge    → Surge price multiplier
- GET  /health           → Service health check
- GET  /models/info      → Last retrain stats

## Laravel Integration
Call this service from your Laravel controllers using Http::post().
See full integration guide in the notebook comments.
