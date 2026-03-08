# RideConnect AI deployment on Render (Docker)

## 1. Prerequisites
- Repository pushed to GitHub.
- `render.yaml` committed at repo root.
- `DATABASE_URL` for PostgreSQL.
- Strong `API_KEY` value.

## 2. Deploy via Render Blueprint
1. In Render, choose **New +** -> **Blueprint**.
2. Connect your GitHub repo and select this project.
3. Render reads `render.yaml` and creates:
- `rideconnect-ai-service` (web service)
- `rideconnect-ai-worker` (background worker)
- `rideconnect-ai-redis` (managed Redis)
4. In Render dashboard, set secret env vars:
- `DATABASE_URL`
- `API_KEY`
5. Deploy all services.

## 3. Healthchecks and runtime
- Web healthcheck path: `/`
- Container command: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}`
- Worker command: `python -m app.worker`
- Service restart policy is managed by Render; failed processes auto-restart.

## 4. Persistent storage notes
- On Docker Compose, `models` and `logs` use persistent named volumes.
- On Render, container filesystem is ephemeral.
- For production model persistence on Render:
1. Build/train models during image build, or
2. Download models from object storage (S3/GCS) at startup, or
3. Attach a Render Disk and mount under `/app/models` (web + worker if needed).

## 5. Scaling guidance
- Scale web service horizontally in Render dashboard.
- Keep model loading deterministic and stateless.
- Keep shared cache/queue in Redis to coordinate across replicas.
- Tune `UVICORN_WORKERS` and instance size based on CPU and p95 latency.

## 6. Optional manual service setup (without Blueprint)
1. Create Redis service in Render, copy internal `connectionString`.
2. Create a Web Service from this repo using Dockerfile.
3. Set env vars from `.env.example`.
4. Create a Worker Service from same repo with command `python -m app.worker`.
5. Point both web and worker `REDIS_URL` to the managed Redis connection string.
