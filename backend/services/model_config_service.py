from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import DoctorUser, ModelConfig
from providers.factory import build_provider_from_model_config


class ModelConfigService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_model_configs(self) -> list[ModelConfig]:
        stmt = select(ModelConfig).order_by(ModelConfig.updated_at.desc(), ModelConfig.id.desc())
        return list(self.db.scalars(stmt))

    def get_model_config(self, config_id: int) -> ModelConfig | None:
        return self.db.get(ModelConfig, config_id)

    def get_active_model_config(self) -> ModelConfig | None:
        stmt = select(ModelConfig).where(ModelConfig.is_active.is_(True)).limit(1)
        return self.db.scalar(stmt)

    def create_model_config(self, **kwargs: Any) -> ModelConfig:
        config = ModelConfig(**kwargs)
        self.db.add(config)
        self.db.flush()
        if config.is_active:
            self._deactivate_others(config.id)
        self.db.commit()
        self.db.refresh(config)
        return config

    def update_model_config(self, config: ModelConfig, **kwargs: Any) -> ModelConfig:
        for key, value in kwargs.items():
            setattr(config, key, value)
        self.db.flush()
        if config.is_active:
            self._deactivate_others(config.id)
        self.db.commit()
        self.db.refresh(config)
        return config

    def delete_model_config(self, config: ModelConfig) -> None:
        self.db.delete(config)
        self.db.commit()

    def set_active(self, config: ModelConfig) -> ModelConfig:
        self._deactivate_others(config.id)
        config.is_active = True
        config.is_enabled = True
        self.db.commit()
        self.db.refresh(config)
        return config

    def set_enabled(self, config: ModelConfig, enabled: bool) -> ModelConfig:
        config.is_enabled = enabled
        if not enabled:
            config.is_active = False
        self.db.commit()
        self.db.refresh(config)
        return config

    def list_doctors(self) -> list[DoctorUser]:
        stmt = select(DoctorUser).order_by(DoctorUser.created_at.desc(), DoctorUser.id.desc())
        return list(self.db.scalars(stmt))

    def doctor_count(self) -> int:
        return int(self.db.scalar(select(func.count()).select_from(DoctorUser)) or 0)

    def model_count(self) -> int:
        return int(self.db.scalar(select(func.count()).select_from(ModelConfig)) or 0)

    def enabled_model_count(self) -> int:
        stmt = select(func.count()).select_from(ModelConfig).where(ModelConfig.is_enabled.is_(True))
        return int(self.db.scalar(stmt) or 0)

    def test_connectivity(self, config: ModelConfig | None = None, payload: dict[str, Any] | None = None) -> tuple[bool, str]:
        provider = build_provider_from_model_config(config=config, payload=payload)
        if not hasattr(provider, "test_connection"):
            return True, "当前提供商无需连通性测试"
        ok, message = provider.test_connection()
        return ok, message

    def _deactivate_others(self, keep_id: int) -> None:
        stmt = select(ModelConfig).where(ModelConfig.id != keep_id, ModelConfig.is_active.is_(True))
        for item in self.db.scalars(stmt):
            item.is_active = False
        self.db.flush()
