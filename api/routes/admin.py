"""Administrative AI routes for retraining and dataset refresh."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import require_api_key

router = APIRouter()


class RetrainRequest(BaseModel):
    models: list[str] | None = None
    triggered_by: str | None = None
    requested_at: str | None = None


@router.post("/admin/build-dataset")
def build_dataset(_: None = Depends(require_api_key)) -> dict:
    from training.dataset_pipeline import extract_and_build_dataset

    dataset = extract_and_build_dataset()
    return {"status": "ok", "rows": int(len(dataset)), "path": "datasets/rides_dataset.csv"}


@router.post("/admin/retrain")
def retrain_models(_: RetrainRequest, __: None = Depends(require_api_key)) -> dict:
    from train_models import run_training_pipeline

    results = run_training_pipeline()
    return {"status": "ok", "results": results}
