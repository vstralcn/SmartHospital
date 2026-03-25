from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from database import SessionLocal
from services.model_config_service import ModelConfigService

router = APIRouter()


class GenerationSettingsUpdate(BaseModel):
    refresh_interval_seconds: int = Field(default=5, ge=1, le=3600)


class SettingsUpdateRequest(BaseModel):
    generation: GenerationSettingsUpdate


@router.get("")
async def get_settings(request: Request):
    storage: Any = request.app.state.storage
    with SessionLocal() as db:
        active_model = ModelConfigService(db).get_active_model_config()
    settings = storage.get_runtime_settings(active_model=active_model)
    llm = settings.get("llm", {})
    if llm.get("api_key"):
        llm["api_key"] = ""
    settings["llm"] = llm
    return settings


@router.put("")
async def update_settings(body: SettingsUpdateRequest, request: Request):
    storage: Any = request.app.state.storage
    current = storage.settings if isinstance(storage.settings, dict) else {}
    next_settings = dict(current)
    next_settings["generation"] = {
        "refresh_interval_seconds": body.generation.refresh_interval_seconds,
    }
    storage.save_settings(next_settings)
    return await get_settings(request)
