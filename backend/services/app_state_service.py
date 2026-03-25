from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from providers.factory import build_provider_from_model_config
from services.llm_service import LLMService
from services.emr_service import EMRService


class AppStateService:
    def __init__(self, prompt_dir: Path) -> None:
        self.prompt_dir = prompt_dir

    def refresh_llm_services(self, app: Any, active_model: Any | None) -> None:
        if active_model is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前没有可用的激活模型配置")
        provider = build_provider_from_model_config(config=active_model)
        llm_service = LLMService(provider=provider, prompt_dir=self.prompt_dir)
        emr_service = EMRService(llm_service=llm_service)
        app.state.llm_service = llm_service
        app.state.emr_service = emr_service
