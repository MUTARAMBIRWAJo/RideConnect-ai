"""Shared API dependencies."""

from __future__ import annotations

from fastapi import Header, HTTPException

from utils.config import settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = settings.api_key
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
