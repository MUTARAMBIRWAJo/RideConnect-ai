"""service.py — Application-wide singletons: DB pool, model loader, Redis helpers.

Both are initialised once during FastAPI lifespan startup and reused
for every request, avoiding per-request connection overhead.
"""

import json
import os
import uuid
from typing import Any, Optional

import databases
import redis.asyncio as redis
from dotenv import load_dotenv

from app.model import PriceModel
from app.utils import logger

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration (sourced from .env / docker-compose environment)
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
API_KEY: str = os.environ.get("API_KEY", "")
MODEL_PATH: str = os.environ.get("MODEL_PATH", "app/price_model.pkl")
REDIS_URL: str = os.environ.get("REDIS_URL", "")
REDIS_QUEUE_NAME: str = os.environ.get("REDIS_QUEUE_NAME", "rideconnect:jobs")
REDIS_QUEUE_ENABLED: bool = os.environ.get("REDIS_QUEUE_ENABLED", "true").lower() == "true"
JOB_RESULT_TTL_SECONDS: int = int(os.environ.get("JOB_RESULT_TTL_SECONDS", "86400"))
DB_ENABLED: bool = bool(DATABASE_URL)

# ---------------------------------------------------------------------------
# Async connection pool (asyncpg driver)
# databases library accepts postgresql:// URLs directly
# ---------------------------------------------------------------------------
class _NoopDatabase:
    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def fetch_one(self, *_args, **_kwargs):
        return None

    async def fetch_all(self, *_args, **_kwargs):
        return []

    async def execute(self, *_args, **_kwargs):
        return None


database = databases.Database(DATABASE_URL) if DB_ENABLED else _NoopDatabase()

# ---------------------------------------------------------------------------
# Model singleton — loaded once, reused for every prediction
# ---------------------------------------------------------------------------
price_model = PriceModel(MODEL_PATH)
redis_client: Optional[redis.Redis] = None


async def init_redis() -> None:
    """Connect Redis if configured; API keeps working if Redis is unavailable."""
    global redis_client
    if not REDIS_URL:
        logger.warning("REDIS_URL is empty; Redis cache/queue disabled.")
        return

    try:
        redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
            health_check_interval=30,
        )
        await redis_client.ping()
        logger.info("Redis connection ready.")
    except Exception as exc:
        redis_client = None
        logger.warning("Redis init failed; running without Redis: %s", exc)


async def close_redis() -> None:
    global redis_client
    if redis_client is None:
        return
    await redis_client.aclose()
    redis_client = None


async def cache_get_json(key: str) -> Optional[dict]:
    if redis_client is None:
        return None
    try:
        raw = await redis_client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.debug("Redis cache get failed for key=%s: %s", key, exc)
        return None


async def cache_set_json(key: str, payload: dict, ttl_seconds: int) -> None:
    if redis_client is None:
        return
    try:
        await redis_client.setex(key, ttl_seconds, json.dumps(payload))
    except Exception as exc:
        logger.debug("Redis cache set failed for key=%s: %s", key, exc)


async def enqueue_job(job_type: str, payload: Optional[dict] = None) -> Optional[str]:
    """Push a background job into Redis list queue and persist queued status."""
    if redis_client is None or not REDIS_QUEUE_ENABLED:
        return None

    payload = payload or {}
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "job_type": job_type,
        "payload": payload,
    }
    try:
        await redis_client.rpush(REDIS_QUEUE_NAME, json.dumps(job))
        await redis_client.setex(
            f"rideconnect:job-status:{job_id}",
            JOB_RESULT_TTL_SECONDS,
            json.dumps({"status": "queued", "job_type": job_type}),
        )
        return job_id
    except Exception as exc:
        logger.warning("Failed to enqueue job type=%s: %s", job_type, exc)
        return None


async def get_job_status(job_id: str) -> Optional[dict[str, Any]]:
    if redis_client is None:
        return None
    try:
        raw = await redis_client.get(f"rideconnect:job-status:{job_id}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Lifecycle helpers (called from main.py lifespan)
# ---------------------------------------------------------------------------
async def startup() -> None:
    if DB_ENABLED:
        await database.connect()
        logger.info("Database connection pool opened.")
    else:
        logger.warning("DATABASE_URL is not set; database-backed endpoints will be degraded.")

    await init_redis()

    price_model.load()
    logger.info("Price model ready — loaded=%s  path=%s", price_model.is_loaded, MODEL_PATH)

    # Enumerate public tables for diagnostic visibility
    if DB_ENABLED:
        try:
            rows = await database.fetch_all(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
            tables = [r["table_name"] for r in rows]
            logger.info("Supabase public tables (%d): %s", len(tables), tables)
        except Exception as exc:
            logger.warning("Schema inspection skipped: %s", exc)


async def shutdown() -> None:
    await close_redis()
    if DB_ENABLED:
        await database.disconnect()
        logger.info("Database connection pool closed.")
