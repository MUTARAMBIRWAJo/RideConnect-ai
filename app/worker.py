"""Redis queue worker for background AI jobs.

Run with:
  python -m app.worker
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from redis import Redis

from app.retraining import run_full_pipeline
from app.utils import logger

REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")
REDIS_QUEUE_NAME: str = os.environ.get("REDIS_QUEUE_NAME", "rideconnect:jobs")
JOB_RESULT_TTL_SECONDS: int = int(os.environ.get("JOB_RESULT_TTL_SECONDS", "86400"))
POLL_TIMEOUT_SECONDS: int = int(os.environ.get("WORKER_POLL_TIMEOUT", "5"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_key(job_id: str) -> str:
    return f"rideconnect:job-status:{job_id}"


def _set_status(client: Redis, job_id: str, payload: dict[str, Any]) -> None:
    client.setex(_status_key(job_id), JOB_RESULT_TTL_SECONDS, json.dumps(payload))


def _process_retrain_job(client: Redis, job_id: str, payload: dict[str, Any]) -> None:
    _set_status(
        client,
        job_id,
        {"status": "running", "job_type": "retrain_models", "started_at": _now()},
    )

    try:
        results = run_full_pipeline()
        _set_status(
            client,
            job_id,
            {
                "status": "completed",
                "job_type": "retrain_models",
                "completed_at": _now(),
                "results": results,
                "requested_models": payload.get("models", []),
            },
        )
        logger.info("Completed retrain job=%s", job_id)
    except Exception as exc:
        _set_status(
            client,
            job_id,
            {
                "status": "failed",
                "job_type": "retrain_models",
                "completed_at": _now(),
                "error": str(exc),
            },
        )
        logger.exception("Retrain job failed job=%s", job_id)


def main() -> None:
    logger.info("Starting worker. queue=%s", REDIS_QUEUE_NAME)
    client = Redis.from_url(REDIS_URL, decode_responses=True)

    while True:
        try:
            item = client.blpop(REDIS_QUEUE_NAME, timeout=POLL_TIMEOUT_SECONDS)
            if item is None:
                continue

            _, raw_job = item
            job = json.loads(raw_job)
            job_id = str(job.get("job_id", "unknown"))
            job_type = str(job.get("job_type", ""))
            payload = job.get("payload", {}) or {}

            if job_type == "retrain_models":
                _process_retrain_job(client, job_id, payload)
            else:
                _set_status(
                    client,
                    job_id,
                    {
                        "status": "failed",
                        "job_type": job_type,
                        "completed_at": _now(),
                        "error": f"Unknown job_type: {job_type}",
                    },
                )
                logger.warning("Unknown job type job=%s type=%s", job_id, job_type)
        except Exception as exc:
            logger.exception("Worker loop error: %s", exc)
            time.sleep(2)


if __name__ == "__main__":
    main()
