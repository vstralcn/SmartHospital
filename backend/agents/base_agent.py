from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from loguru import logger

from utils.json_utils import parse_json_from_text

from .llm_adapter import ProviderLLM
from .messages import AgentMessage

LogSink = Callable[[Dict[str, Any]], None]


def _estimate_tokens(text: str) -> int:
    """Rough token estimate that works for mixed CJK / ASCII text.

    Real usage is not always returned by every provider (and the Mock
    provider returns none), so the monitor relies on this deterministic
    estimate to display non-zero, comparable numbers across agents.
    """

    if not text:
        return 0
    return max(1, math.ceil(len(text) / 2))


class BaseAgent:
    """Base class for every collaborating agent.

    Subclasses implement :meth:`handle` to transform an incoming
    :class:`AgentMessage` payload into their own result payload. The base
    class wraps that call with timing, status tracking, token accounting and
    structured logging so the orchestrator and the frontend monitor get a
    consistent execution record for every node.
    """

    name: str = "base_agent"
    role_prompt: str = "You are a helpful medical assistant."

    def __init__(
        self,
        provider: Any,
        mcp_registry: Any | None = None,
        log_sink: Optional[LogSink] = None,
    ) -> None:
        self.provider = provider
        self.mcp = mcp_registry
        self.log_sink = log_sink
        self.llm = ProviderLLM(provider=provider, system_prompt=self.role_prompt)
        self._chain = PromptTemplate.from_template("{input}") | self.llm | StrOutputParser()
        # per-run accumulators (reset at the start of every run)
        self._tokens_in = 0
        self._tokens_out = 0
        self._llm_calls = 0
        self._tool_calls: List[Dict[str, Any]] = []

    # -- LLM + tool helpers used by subclasses -----------------------------
    def invoke_llm(self, user_prompt: str) -> str:
        self._tokens_in += _estimate_tokens(self.role_prompt) + _estimate_tokens(user_prompt)
        text = self._chain.invoke({"input": user_prompt})
        self._tokens_out += _estimate_tokens(text)
        self._llm_calls += 1
        return text or ""

    def invoke_llm_json(self, user_prompt: str) -> Any:
        text = self.invoke_llm(user_prompt)
        return parse_json_from_text(text)

    def call_tool(self, tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        if self.mcp is None:
            result = {"ok": False, "error": "MCP registry 未配置", "data": None}
        else:
            result = self.mcp.call(tool_name, **kwargs)
        self._tool_calls.append(
            {"tool": tool_name, "args": kwargs, "ok": result.get("ok", False)}
        )
        return result

    # -- subclass contract -------------------------------------------------
    def handle(self, message: AgentMessage) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    # -- orchestration entry point -----------------------------------------
    def run(self, message: AgentMessage, target: str) -> AgentMessage:
        self._tokens_in = 0
        self._tokens_out = 0
        self._llm_calls = 0
        self._tool_calls = []

        started_at = datetime.now(timezone.utc)
        start_perf = time.perf_counter()
        status = "success"
        error_text = ""
        result_payload: Dict[str, Any] = {}

        try:
            result_payload = self.handle(message)
        except Exception as exc:  # noqa: BLE001 - record failure, keep pipeline alive
            status = "error"
            error_text = str(exc)
            logger.exception(f"Agent {self.name} failed: {exc}")
            result_payload = {self.name: {"error": error_text}}

        duration_ms = int((time.perf_counter() - start_perf) * 1000)
        ended_at = datetime.now(timezone.utc)

        record = {
            "task_id": message.task_id,
            "session_id": str(message.payload.get("session_id", "")),
            "agent_name": self.name,
            "status": status,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "prompt_tokens": self._tokens_in,
            "completion_tokens": self._tokens_out,
            "total_tokens": self._tokens_in + self._tokens_out,
            "llm_calls": self._llm_calls,
            "tool_calls": list(self._tool_calls),
            "input_payload": self._summarize_input(message.payload),
            "output_payload": result_payload,
            "error": error_text,
        }
        self._emit_log(record)

        return message.reply(source=self.name, target=target, payload=result_payload)

    # -- internal helpers --------------------------------------------------
    def _summarize_input(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        keys = [
            "session_id",
            "interview",
            "diagnosis",
            "drug",
            "emr",
        ]
        return {k: payload[k] for k in keys if k in payload}

    def _emit_log(self, record: Dict[str, Any]) -> None:
        if self.log_sink is None:
            return
        try:
            self.log_sink(record)
        except Exception as exc:  # noqa: BLE001 - logging must never break the flow
            logger.warning(f"Failed to persist agent log for {self.name}: {exc}")
