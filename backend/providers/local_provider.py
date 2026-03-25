from __future__ import annotations

from .base_provider import BaseLLMProvider


class LocalProvider(BaseLLMProvider):
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url
        self.model = model

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        raise NotImplementedError("LocalProvider is reserved for future local model integration.")

    def test_connection(self) -> tuple[bool, str]:
        return False, "本地模型连通性测试暂未实现"
