from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Admin, AsrConfig, ModelConfig
from services.auth_service import AuthService

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_MODEL_NAME = "默认演示模型"
DEFAULT_ASR_NAME = "默认腾讯云 ASR"


class AdminBootstrapService:
    def __init__(
        self,
        db: Session,
        auth_service: AuthService,
        yaml_settings: dict[str, object] | None = None,
    ) -> None:
        self.db = db
        self.auth_service = auth_service
        self.yaml_settings = yaml_settings or {}

    def bootstrap(self) -> None:
        self._ensure_default_admin()
        self._ensure_default_model_config()
        self._ensure_default_asr_config()
        self.db.commit()

    def _ensure_default_admin(self) -> None:
        stmt = select(Admin).where(Admin.username == DEFAULT_ADMIN_USERNAME).limit(1)
        admin = self.db.scalar(stmt)
        if admin is None:
            self.db.add(
                Admin(
                    username=DEFAULT_ADMIN_USERNAME,
                    password_hash=self.auth_service.hash_password(
                        DEFAULT_ADMIN_PASSWORD
                    ),
                    is_active=True,
                )
            )

    def _ensure_default_model_config(self) -> None:
        llm = (
            self.yaml_settings.get("llm", {})
            if isinstance(self.yaml_settings, dict)
            else {}
        )
        provider = os.getenv("LLM_PROVIDER", str(llm.get("provider", "mock") or "mock"))
        model = os.getenv(
            "LLM_MODEL", str(llm.get("model", "gpt-4o-mini") or "gpt-4o-mini")
        )
        api_key = os.getenv("OPENAI_API_KEY", str(llm.get("api_key", "") or ""))
        base_url = os.getenv("OPENAI_BASE_URL", str(llm.get("base_url", "") or ""))
        raw_temperature = os.getenv("LLM_TEMPERATURE", llm.get("temperature", 1.0))
        temperature = (
            float(raw_temperature) if raw_temperature not in (None, "") else None
        )

        config = self.db.scalar(
            select(ModelConfig).where(ModelConfig.name == DEFAULT_MODEL_NAME).limit(1)
        )
        if config is None:
            config = ModelConfig(name=DEFAULT_MODEL_NAME)
            self.db.add(config)
            self.db.flush()

        config.provider = provider
        config.model = model
        config.api_key = api_key
        config.base_url = base_url
        config.temperature = temperature
        config.is_active = True
        config.is_enabled = True

        for item in self.db.scalars(
            select(ModelConfig).where(
                ModelConfig.id != config.id, ModelConfig.is_active.is_(True)
            )
        ):
            item.is_active = False

    def _ensure_default_asr_config(self) -> None:
        appid = os.getenv("TENCENT_ASR_APPID", "").strip()
        secret_id = os.getenv("TENCENT_ASR_SECRET_ID", "").strip()
        secret_key = os.getenv("TENCENT_ASR_SECRET_KEY", "").strip()
        engine_model_type = (
            os.getenv("TENCENT_ASR_ENGINE_MODEL_TYPE", "16k_zh").strip() or "16k_zh"
        )

        if not (appid and secret_id and secret_key):
            return

        config = self.db.scalar(
            select(AsrConfig).where(AsrConfig.name == DEFAULT_ASR_NAME).limit(1)
        )
        if config is None:
            config = AsrConfig(
                name=DEFAULT_ASR_NAME,
                appid=appid,
                secret_id=secret_id,
                secret_key=secret_key,
                engine_model_type=engine_model_type,
                is_active=True,
                is_enabled=True,
            )
            self.db.add(config)
            self.db.flush()
        else:
            config.appid = appid
            config.secret_id = secret_id
            config.secret_key = secret_key
            config.engine_model_type = engine_model_type
            config.is_active = True
            config.is_enabled = True

        for item in self.db.scalars(
            select(AsrConfig).where(
                AsrConfig.id != config.id, AsrConfig.is_active.is_(True)
            )
        ):
            item.is_active = False
