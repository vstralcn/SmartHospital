from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        raise NotImplementedError

    def test_connection(self) -> tuple[bool, str]:
        return True, "当前提供商无需连通性测试"
