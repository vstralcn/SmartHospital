from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import AsrConfig
from routers.admin_auth_router import get_current_admin
from services.tencent_asr_service import TencentAsrService

router = APIRouter(prefix="/api/admin/asr", dependencies=[Depends(get_current_admin)])

tencent_asr_service = TencentAsrService()


class AsrConfigCreate(BaseModel):
    name: str
    appid: str
    secret_id: str
    secret_key: str
    engine_model_type: str = Field(default="16k_zh")
    is_active: bool = False
    is_enabled: bool = True


class AsrConfigUpdate(BaseModel):
    name: str
    appid: str
    secret_id: str
    secret_key: str = ""
    engine_model_type: str = Field(default="16k_zh")
    is_enabled: bool = True
    is_active: bool = False


def _serialize(config: AsrConfig) -> dict[str, Any]:
    masked_id = ""
    if config.secret_id:
        masked_id = f"{config.secret_id[:6]}***{config.secret_id[-4:]}" if len(config.secret_id) > 10 else config.secret_id
    return {
        "id": config.id,
        "name": config.name,
        "appid": config.appid,
        "secret_id_masked": masked_id,
        "engine_model_type": config.engine_model_type,
        "is_active": config.is_active,
        "is_enabled": config.is_enabled,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


def _get_or_404(db: Session, config_id: int) -> AsrConfig:
    config = db.get(AsrConfig, config_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ASR 配置不存在")
    return config


def _deactivate_others(db: Session, keep_id: int) -> None:
    stmt = select(AsrConfig).where(AsrConfig.id != keep_id, AsrConfig.is_active.is_(True))
    for item in db.scalars(stmt):
        item.is_active = False
    db.flush()


@router.get("")
def list_asr_configs(db: Session = Depends(get_db)):
    stmt = select(AsrConfig).order_by(AsrConfig.updated_at.desc(), AsrConfig.id.desc())
    return [_serialize(c) for c in db.scalars(stmt)]


@router.post("")
def create_asr_config(body: AsrConfigCreate, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["appid"] = data["appid"].strip()
    data["secret_id"] = data["secret_id"].strip()
    data["secret_key"] = data["secret_key"].strip()
    config = AsrConfig(**data)
    db.add(config)
    db.flush()
    if config.is_active:
        _deactivate_others(db, config.id)
    db.commit()
    db.refresh(config)
    return _serialize(config)


@router.put("/{config_id}")
def update_asr_config(config_id: int, body: AsrConfigUpdate, db: Session = Depends(get_db)):
    config = _get_or_404(db, config_id)
    config.name = body.name
    config.appid = body.appid.strip()
    config.secret_id = body.secret_id.strip()
    if body.secret_key:
        config.secret_key = body.secret_key.strip()
    config.engine_model_type = body.engine_model_type
    config.is_enabled = body.is_enabled
    config.is_active = body.is_active
    db.flush()
    if config.is_active:
        _deactivate_others(db, config.id)
    db.commit()
    db.refresh(config)
    return _serialize(config)


@router.delete("/{config_id}")
def delete_asr_config(config_id: int, db: Session = Depends(get_db)):
    config = _get_or_404(db, config_id)
    db.delete(config)
    db.commit()
    return {"message": "删除成功"}


@router.post("/{config_id}/activate")
def activate_asr_config(config_id: int, db: Session = Depends(get_db)):
    config = _get_or_404(db, config_id)
    if not config.is_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先启用该 ASR 配置")
    _deactivate_others(db, config.id)
    config.is_active = True
    config.is_enabled = True
    db.commit()
    db.refresh(config)
    return _serialize(config)


@router.post("/{config_id}/enable")
def enable_asr_config(config_id: int, enabled: bool, db: Session = Depends(get_db)):
    config = _get_or_404(db, config_id)
    config.is_enabled = enabled
    if not enabled:
        config.is_active = False
    db.commit()
    db.refresh(config)
    return _serialize(config)


@router.post("/{config_id}/test")
async def test_asr_config(config_id: int, db: Session = Depends(get_db)):
    config = _get_or_404(db, config_id)
    try:
        import websockets

        url = tencent_asr_service.generate_sign_url(
            appid=config.appid,
            secret_id=config.secret_id,
            secret_key=config.secret_key,
            engine_model_type=config.engine_model_type,
        )
        ws = await asyncio.wait_for(websockets.connect(url), timeout=10)
        init_msg = await asyncio.wait_for(ws.recv(), timeout=10)
        import json
        result = json.loads(init_msg)
        await ws.close()
        if result.get("code") == 0:
            return {"success": True, "message": "连接成功，腾讯云 ASR 握手通过"}
        return {"success": False, "message": f"握手失败：{result.get('message', '未知错误')}"}
    except asyncio.TimeoutError:
        return {"success": False, "message": "连接超时，请检查网络或配置"}
    except Exception as e:
        return {"success": False, "message": f"连接失败：{str(e)}"}
