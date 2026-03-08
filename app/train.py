"""train.py — Convenience entry point for the production training pipeline.

Delegates entirely to app.train_model which contains the full logic for
fetching real ride data from Supabase, engineering features, training the
RandomForestRegressor, and saving the model.

Usage:
    python -m app.train                              # from project root
    docker exec rideconnect_ai python -m app.train   # inside container
"""

from app.train_model import main

if __name__ == "__main__":
    main()
