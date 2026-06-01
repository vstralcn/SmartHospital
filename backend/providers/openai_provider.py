from __future__ import annotations

from typing import Any, cast

from loguru import logger

from .base_provider import BaseLLMProvider

# ---------- JSON-Schema response formats ----------

_STRUCTURED_EMR_FIELDS = {
    "chief_complaint": {"type": "string"},
    "present_illness": {"type": "string"},
    "past_history": {"type": "string"},
    "surgical_history": {"type": "string"},
    "allergy_history": {"type": "string"},
    "medication_history": {"type": "string"},
    "family_history": {"type": "string"},
    "missing_info": {"type": "array", "items": {"type": "string"}},
    "needs_confirmation": {"type": "array", "items": {"type": "string"}},
}

_STRUCTURED_EMR_REQUIRED = [
    "chief_complaint",
    "present_illness",
    "past_history",
    "surgical_history",
    "allergy_history",
    "medication_history",
    "family_history",
    "missing_info",
    "needs_confirmation",
]

_FORMAT_STRUCTURED_EXTRACT: dict = {
    "type": "json_schema",
    "json_schema": {
        "name": "structured_emr",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": _STRUCTURED_EMR_FIELDS,
            "required": _STRUCTURED_EMR_REQUIRED,
            "additionalProperties": False,
        },
    },
}

_FORMAT_ALIGNED_EMR: dict = {
    "type": "json_schema",
    "json_schema": {
        "name": "aligned_emr",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "structured": {
                    "type": "object",
                    "properties": _STRUCTURED_EMR_FIELDS,
                    "required": _STRUCTURED_EMR_REQUIRED,
                    "additionalProperties": False,
                },
                "emr_text": {"type": "string"},
            },
            "required": ["structured", "emr_text"],
            "additionalProperties": False,
        },
    },
}

# Map prompt_type (first line of system_prompt) → response_format
_RESPONSE_FORMAT_MAP: dict[str, dict] = {
    "structured_extract": _FORMAT_STRUCTURED_EXTRACT,
    "aligned_emr_generation": _FORMAT_ALIGNED_EMR,
}


class OpenAIProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        temperature: float | None = None,
    ) -> None:
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature

    def _build_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is required for OpenAIProvider") from exc

        if self.base_url:
            return OpenAI(api_key=self.api_key, base_url=self.base_url)
        return OpenAI(api_key=self.api_key)

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        client = self._build_client()

        prompt_type = (system_prompt or "").splitlines()[0].strip()
        effective_system_prompt = system_prompt or "You are a medical documentation assistant."
        if "\n\n" in effective_system_prompt:
            effective_system_prompt = effective_system_prompt.split("\n\n", 1)[1]

        messages = cast(
            Any,
            [
                {"role": "system", "content": effective_system_prompt},
                {"role": "user", "content": prompt},
            ],
        )

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "timeout": 300,
        }
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        response_format = _RESPONSE_FORMAT_MAP.get(prompt_type)
        if response_format is not None:
            try:
                kwargs["response_format"] = response_format
                response = client.chat.completions.create(**kwargs)
            except Exception:
                # Fallback: some providers don't support response_format
                logger.warning(f"response_format not supported for {prompt_type}, falling back")
                kwargs.pop("response_format", None)
                response = client.chat.completions.create(**kwargs)
        else:
            response = client.chat.completions.create(**kwargs)

        if not response.choices:
            return ""
        message = response.choices[0].message
        return message.content or ""

    def test_connection(self) -> tuple[bool, str]:
        if not self.api_key.strip():
            return False, "API Key 不能为空"
        try:
            client = self._build_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                timeout=10,
            )
            if not response.choices:
                return False, "模型返回为空"
            return True, "连通性测试成功"
        except Exception as exc:
            return False, f"连通性测试失败：{exc}"
