from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException, status

from agents.orchestrator import Orchestrator
from providers.factory import build_provider_from_model_config
from services.agent_log_service import AgentLogService
from services.emr_service import EMRService
from services.llm_service import LLMService


def _persist_agent_log(record: Dict[str, Any]) -> None:
    """Log sink used by the orchestrator.

    Runs inside the agent worker thread, so it opens its own short-lived DB
    session to stay isolated from the request-scoped session.
    """

    from database import SessionLocal

    with SessionLocal() as db:
        AgentLogService(db).record(record)


class AppStateService:
    def __init__(self, prompt_dir: Path, mcp_registry: Any | None = None) -> None:
        self.prompt_dir = prompt_dir
        self.mcp_registry = mcp_registry

    def refresh_llm_services(self, app: Any, active_model: Any | None) -> None:
        if active_model is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前没有可用的激活模型配置")
        provider = build_provider_from_model_config(config=active_model)
        llm_service = LLMService(provider=provider, prompt_dir=self.prompt_dir)
        emr_service = EMRService(llm_service=llm_service)
        orchestrator = Orchestrator(
            provider=provider,
            mcp_registry=self.mcp_registry,
            log_sink=_persist_agent_log,
        )
        app.state.llm_service = llm_service
        app.state.emr_service = emr_service
        app.state.orchestrator = orchestrator
