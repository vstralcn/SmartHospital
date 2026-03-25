from __future__ import annotations

import os
from typing import Any

from loguru import logger

from models import ModelConfig

from .local_provider import LocalProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAIProvider


def _normalize_temperature(raw_temperature: Any) -> float | None:
    return float(raw_temperature) if raw_temperature is not None and raw_temperature != "" else None


def _build_provider(provider_name: str, model_name: str, api_key: str = "", base_url: str | None = None, temperature: float | None = None):
    provider_name = str(provider_name or "mock").lower()
    model_name = str(model_name or "gpt-4o-mini")

    if provider_name == "openai":
        api_key = str(api_key or os.getenv("OPENAI_API_KEY", ""))
        base_url = str(base_url or "").strip() or None
        if api_key:
            return OpenAIProvider(
                api_key=api_key,
                model=model_name,
                base_url=base_url,
                temperature=temperature,
            )
        logger.warning("OpenAI API key is missing, falling back to MockProvider")
        return MockProvider()

    if provider_name == "local":
        return LocalProvider(base_url=str(base_url or "http://127.0.0.1:8000"), model=model_name)

    return MockProvider()


def build_provider(settings: dict):
    llm_settings = settings.get("llm", {})
    return _build_provider(
        provider_name=str(llm_settings.get("provider", "mock")),
        model_name=str(llm_settings.get("model", "gpt-4o-mini")),
        api_key=str(llm_settings.get("api_key", "") or ""),
        base_url=str(llm_settings.get("base_url", "") or ""),
        temperature=_normalize_temperature(llm_settings.get("temperature", None)),
    )


def build_provider_from_model_config(config: ModelConfig | None = None, payload: dict[str, Any] | None = None):
    if config is not None:
        return _build_provider(
            provider_name=config.provider,
            model_name=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
        )

    payload = payload or {}
    return _build_provider(
        provider_name=str(payload.get("provider", "mock")),
        model_name=str(payload.get("model", "gpt-4o-mini")),
        api_key=str(payload.get("api_key", "") or ""),
        base_url=str(payload.get("base_url", "") or ""),
        temperature=_normalize_temperature(payload.get("temperature", None)),
    )
