"""service.py — Application-wide singletons: DB pool and model loader.

Both are initialised once during FastAPI lifespan startup and reused
for every request, avoiding per-request connection overhead.
"""

import os

import databases
from dotenv import load_dotenv

from app.model import PriceModel
from app.utils import logger

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration (sourced from .env / docker-compose environment)
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.environ["DATABASE_URL"]
API_KEY: str = os.environ.get("API_KEY", "")
MODEL_PATH: str = os.environ.get("MODEL_PATH", "app/price_model.pkl")

# ---------------------------------------------------------------------------
# Async connection pool (asyncpg driver)
# databases library accepts postgresql:// URLs directly
# ---------------------------------------------------------------------------
database = databases.Database(DATABASE_URL)

# ---------------------------------------------------------------------------
# Model singleton — loaded once, reused for every prediction
# ---------------------------------------------------------------------------
price_model = PriceModel(MODEL_PATH)


# ---------------------------------------------------------------------------
# Lifecycle helpers (called from main.py lifespan)
# ---------------------------------------------------------------------------
async def startup() -> None:
    await database.connect()
    logger.info("Database connection pool opened.")

    price_model.load()
    logger.info("Price model ready — loaded=%s  path=%s", price_model.is_loaded, MODEL_PATH)

    # Enumerate public tables for diagnostic visibility
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
    await database.disconnect()
    logger.info("Database connection pool closed.")
