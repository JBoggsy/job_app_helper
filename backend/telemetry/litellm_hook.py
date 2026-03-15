"""LiteLLM callback for capturing per-LLM-call metrics.

Automatically records model, token counts, latency, and cost for every
LLM call made through litellm.completion() — including calls from DSPy
modules and raw litellm usage (e.g., the result collator).

Register once at app startup:
    from backend.telemetry.litellm_hook import register_litellm_callback
    register_litellm_callback()
"""

from __future__ import annotations

import logging

import litellm
from litellm.integrations.custom_logger import CustomLogger

from backend.telemetry.collector import get_collector
from backend.telemetry.context import current_run_id, current_trace_id

logger = logging.getLogger(__name__)


class TelemetryLiteLLMCallback(CustomLogger):
    """LiteLLM callback that records LLM call metrics to telemetry."""

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        collector = get_collector()
        if collector is None:
            return

        try:
            # Extract usage info
            usage = getattr(response_obj, "usage", None)
            tokens_in = getattr(usage, "prompt_tokens", None) if usage else None
            tokens_out = getattr(usage, "completion_tokens", None) if usage else None

            # Latency
            latency_ms = None
            if start_time and end_time:
                latency_ms = int((end_time - start_time).total_seconds() * 1000)

            # Cost (LiteLLM may calculate this)
            cost_usd = None
            hidden = getattr(response_obj, "_hidden_params", {})
            if isinstance(hidden, dict):
                cost_usd = hidden.get("response_cost")

            collector.record_llm_call(
                run_id=current_run_id.get(),
                module_trace_id=current_trace_id.get(),
                model=kwargs.get("model"),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
            )
        except Exception:
            logger.debug("Telemetry: failed to record LLM call", exc_info=True)

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        # Record failed calls too — useful for tracking error rates
        collector = get_collector()
        if collector is None:
            return

        try:
            latency_ms = None
            if start_time and end_time:
                latency_ms = int((end_time - start_time).total_seconds() * 1000)

            collector.record_llm_call(
                run_id=current_run_id.get(),
                module_trace_id=current_trace_id.get(),
                model=kwargs.get("model"),
                tokens_in=None,
                tokens_out=None,
                latency_ms=latency_ms,
                cost_usd=None,
            )
        except Exception:
            logger.debug("Telemetry: failed to record LLM failure", exc_info=True)


def register_litellm_callback() -> None:
    """Add the telemetry callback to LiteLLM's callback list.

    Safe to call multiple times — checks for duplicates.
    """
    for cb in litellm.callbacks:
        if isinstance(cb, TelemetryLiteLLMCallback):
            return
    litellm.callbacks.append(TelemetryLiteLLMCallback())
    logger.info("Telemetry LiteLLM callback registered")
