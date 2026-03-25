from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import ModelConfig
from routers.admin_auth_router import get_current_admin
from services.model_config_service import ModelConfigService

router = APIRouter(prefix="/api/admin/models", dependencies=[Depends(get_current_admin)])


class ModelConfigBase(BaseModel):
    name: str
    provider: str = Field(default="mock")
    model: str = Field(default="gpt-4o-mini")
    base_url: str = ""
    temperature: float | None = 1.0
    is_enabled: bool = True


class ModelConfigCreate(ModelConfigBase):
    api_key: str = ""
    is_active: bool = False


class ModelConfigUpdate(BaseModel):
    name: str
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""
    temperature: float | None = 1.0
    is_enabled: bool = True
    is_active: bool = False


class ModelConfigTestPayload(BaseModel):
    provider: str = "mock"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    temperature: float | None = 1.0


def serialize_model_config(config: ModelConfig) -> dict[str, Any]:
    masked_key = ""
    if config.api_key:
        masked_key = f"{config.api_key[:3]}***{config.api_key[-4:]}" if len(config.api_key) > 7 else "***"
    return {
        "id": config.id,
        "name": config.name,
        "provider": config.provider,
        "model": config.model,
        "api_key_masked": masked_key,
        "base_url": config.base_url,
        "temperature": config.temperature,
        "is_active": config.is_active,
        "is_enabled": config.is_enabled,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


def _get_config_or_404(service: ModelConfigService, config_id: int) -> ModelConfig:
    config = service.get_model_config(config_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模型配置不存在")
    return config


@router.get("")
def list_models(db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    return [serialize_model_config(item) for item in service.list_model_configs()]


@router.post("")
def create_model(body: ModelConfigCreate, request: Request, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    config = service.create_model_config(**body.model_dump())
    if config.is_active:
        request.app.state.app_state_service.refresh_llm_services(request.app, config)
    return serialize_model_config(config)


@router.put("/{config_id}")
def update_model(config_id: int, body: ModelConfigUpdate, request: Request, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    config = _get_config_or_404(service, config_id)
    payload = body.model_dump()
    if not payload["api_key"]:
        payload["api_key"] = config.api_key
    config = service.update_model_config(config, **payload)
    active = service.get_active_model_config()
    if active is not None:
        request.app.state.app_state_service.refresh_llm_services(request.app, active)
    return serialize_model_config(config)


@router.delete("/{config_id}")
def delete_model(config_id: int, request: Request, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    config = _get_config_or_404(service, config_id)
    was_active = config.is_active
    service.delete_model_config(config)
    if was_active:
        active = service.get_active_model_config()
        if active is not None:
            request.app.state.app_state_service.refresh_llm_services(request.app, active)
    return {"message": "删除成功"}


@router.post("/{config_id}/activate")
def activate_model(config_id: int, request: Request, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    config = _get_config_or_404(service, config_id)
    if not config.is_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先启用该模型配置")
    config = service.set_active(config)
    request.app.state.app_state_service.refresh_llm_services(request.app, config)
    return serialize_model_config(config)


@router.post("/{config_id}/enable")
def enable_model(config_id: int, enabled: bool, request: Request, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    config = _get_config_or_404(service, config_id)
    config = service.set_enabled(config, enabled)
    active = service.get_active_model_config()
    if active is not None:
        request.app.state.app_state_service.refresh_llm_services(request.app, active)
    return serialize_model_config(config)


@router.post("/{config_id}/test")
def test_model(config_id: int, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    config = _get_config_or_404(service, config_id)
    ok, message = service.test_connectivity(config=config)
    return {"success": ok, "message": message}


@router.post("/test")
def test_temporary_model(body: ModelConfigTestPayload, db: Session = Depends(get_db)):
    service = ModelConfigService(db)
    ok, message = service.test_connectivity(payload=body.model_dump())
    return {"success": ok, "message": message}
