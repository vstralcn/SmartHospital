from __future__ import annotations

from typing import Any, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM
from pydantic import ConfigDict


class ProviderLLM(LLM):
    """LangChain ``LLM`` that delegates to the project's provider abstraction.

    This adapter lets the multi-agent layer build standard LangChain runnables
    (``PromptTemplate | llm | parser``) while still routing every completion
    through the existing OpenAI / Local / Mock provider system configured in
    the admin console. Each agent owns a ``ProviderLLM`` carrying its own
    system prompt.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: Any
    system_prompt: str = "You are a medical documentation assistant."

    @property
    def _llm_type(self) -> str:
        return "smarthospital-provider"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        return self.provider.generate(prompt, system_prompt=self.system_prompt) or ""
