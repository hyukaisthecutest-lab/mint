from __future__ import annotations
import logging
import time
from typing import Any
from uuid import UUID
from opentelemetry import trace
from langchain_core.callbacks.base import BaseCallbackHandler
from app.core.telemetry import (
    tracer, agent_errors,
    agent_duration, tool_calls, token_usage,
)
from app.core.metrics_store import store

logger = logging.getLogger("mint.agent")


class AgentObserver(BaseCallbackHandler):
    """Creates OTEL child spans and records Prometheus metrics for every agent step."""

    def __init__(self) -> None:
        self._t: dict[UUID, float] = {}
        self._spans: dict[UUID, Any] = {}
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0

    # ── LLM ──────────────────────────────────────────────────────────────────

    def on_chat_model_start(self, serialized: dict, messages: list, *, run_id: UUID, **kw: Any) -> None:
        self._t[run_id] = time.perf_counter()
        model = serialized.get("kwargs", {}).get("model_name", "gpt-4o")
        span = tracer.start_span("llm.chat", attributes={"llm.model": model, "run_id": str(run_id)})
        self._spans[run_id] = span
        logger.info("llm_start", extra={"extra": {"run_id": str(run_id), "model": model}})

    def on_llm_end(self, response: Any, *, run_id: UUID, **kw: Any) -> None:
        elapsed = time.perf_counter() - self._t.pop(run_id, time.perf_counter())
        usage = {}
        if response.llm_output:
            usage = response.llm_output.get("token_usage", {})
        prompt_t = usage.get("prompt_tokens", 0)
        completion_t = usage.get("completion_tokens", 0)
        self.total_prompt_tokens += prompt_t
        self.total_completion_tokens += completion_t
        token_usage.labels(type="prompt").inc(prompt_t)
        token_usage.labels(type="completion").inc(completion_t)
        store.record_tokens(prompt_t, completion_t)
        agent_duration.labels(step="llm").observe(elapsed)
        span = self._spans.pop(run_id, None)
        if span:
            span.set_attribute("llm.prompt_tokens", prompt_t)
            span.set_attribute("llm.completion_tokens", completion_t)
            span.end()
        logger.info("llm_end", extra={"extra": {
            "run_id": str(run_id), "elapsed_s": round(elapsed, 3),
            "prompt_tokens": prompt_t, "completion_tokens": completion_t,
        }})

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kw: Any) -> None:
        elapsed = time.perf_counter() - self._t.pop(run_id, time.perf_counter())
        agent_errors.labels(step="llm").inc()
        agent_duration.labels(step="llm").observe(elapsed)
        span = self._spans.pop(run_id, None)
        if span:
            span.set_status(trace.StatusCode.ERROR, str(error))
            span.end()
        logger.error("llm_error", extra={"extra": {"run_id": str(run_id), "error": str(error)}})

    # ── Tools ─────────────────────────────────────────────────────────────────

    def on_tool_start(self, serialized: dict, input_str: str, *, run_id: UUID, **kw: Any) -> None:
        self._t[run_id] = time.perf_counter()
        tool_name = serialized.get("name", "unknown")
        span = tracer.start_span("tool.call", attributes={"tool.name": tool_name, "tool.input": input_str[:300]})
        self._spans[run_id] = span
        logger.info("tool_start", extra={"extra": {"run_id": str(run_id), "tool": tool_name, "input": input_str[:200]}})

    def on_tool_end(self, output: str, *, run_id: UUID, **kw: Any) -> None:
        elapsed = time.perf_counter() - self._t.pop(run_id, time.perf_counter())
        span = self._spans.pop(run_id, None)
        tool_name_val = span.attributes.get("tool.name", "unknown") if span else "unknown"
        tool_calls.labels(tool=tool_name_val, success="true").inc()
        store.record_tool(tool_name_val)
        agent_duration.labels(step="tool").observe(elapsed)
        if span:
            span.set_attribute("tool.output", str(output)[:300])
            span.end()
        logger.info("tool_end", extra={"extra": {"run_id": str(run_id), "elapsed_s": round(elapsed, 3), "output": str(output)[:200]}})

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kw: Any) -> None:
        elapsed = time.perf_counter() - self._t.pop(run_id, time.perf_counter())
        span = self._spans.pop(run_id, None)
        tool_name = span.attributes.get("tool.name", "unknown") if span else "unknown"
        tool_calls.labels(tool=tool_name, success="false").inc()
        agent_errors.labels(step="tool").inc()
        agent_duration.labels(step="tool").observe(elapsed)
        if span:
            span.set_status(trace.StatusCode.ERROR, str(error))
            span.end()
        logger.error("tool_error", extra={"extra": {"run_id": str(run_id), "tool": tool_name, "error": str(error)}})
