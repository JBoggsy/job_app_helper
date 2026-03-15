"""Telemetry context propagation via contextvars.

Provides ContextVars for tracking the current run and module trace IDs
through the call stack, plus a context manager for run lifecycle.

Usage:
    from backend.telemetry.context import telemetry_run

    def run(self, messages):
        with telemetry_run(conversation_id, user_message, "my_design"):
            # ... all child module traces and tool calls are auto-linked ...
"""

from __future__ import annotations

import contextvars
import functools
import logging
import time
from contextlib import contextmanager
from typing import Any, Callable

from backend.telemetry.collector import _uuid_short, get_collector

logger = logging.getLogger(__name__)

# ── Context variables ──

current_run_id = contextvars.ContextVar[str | None](
    "telemetry_run_id", default=None,
)
current_trace_id = contextvars.ContextVar[str | None](
    "telemetry_trace_id", default=None,
)


# ── Run lifecycle context manager ──

@contextmanager
def telemetry_run(
    conversation_id: int | None,
    user_message: str | None,
    design_name: str,
):
    """Context manager wrapping an entire agent run.

    Sets current_run_id for the duration of the block so all child
    module traces, tool calls, and workflow traces are linked to this run.

    If telemetry is disabled (no collector), yields None and acts as a no-op.
    """
    collector = get_collector()
    if collector is None:
        yield None
        return

    run_id = _uuid_short()
    token = current_run_id.set(run_id)
    t0 = time.monotonic()

    try:
        collector.record_run_start(run_id, conversation_id, design_name, user_message)
    except Exception:
        logger.debug("Telemetry: failed to record run start", exc_info=True)

    try:
        yield run_id
    except Exception as exc:
        _record_run_end(collector, run_id, t0, success=False, error=str(exc))
        raise
    else:
        _record_run_end(collector, run_id, t0, success=True)
    finally:
        current_run_id.reset(token)


def _record_run_end(
    collector: Any, run_id: str, t0: float,
    success: bool, error: str | None = None,
    final_response: str | None = None,
) -> None:
    try:
        duration_ms = int((time.monotonic() - t0) * 1000)
        collector.record_run_end(
            run_id, success=success, duration_ms=duration_ms,
            error=error, final_response=final_response,
        )
    except Exception:
        logger.debug("Telemetry: failed to record run end", exc_info=True)


# ── ThreadPoolExecutor context propagation ──

def copy_telemetry_context(fn: Callable) -> Callable:
    """Wrap a callable to copy the current telemetry context into the new thread.

    Use when submitting work to a ThreadPoolExecutor:

        executor.submit(copy_telemetry_context(my_func), arg1, arg2)
    """
    ctx = contextvars.copy_context()

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return ctx.run(fn, *args, **kwargs)

    return wrapper


class TracedThreadPoolExecutor:
    """Drop-in wrapper around ThreadPoolExecutor that propagates telemetry context.

    Usage (replace ``ThreadPoolExecutor`` with ``TracedThreadPoolExecutor``):

        from backend.telemetry.context import TracedThreadPoolExecutor
        with TracedThreadPoolExecutor(max_workers=3) as pool:
            pool.submit(my_func, arg1)
    """

    def __init__(self, *args: Any, **kwargs: Any):
        from concurrent.futures import ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(*args, **kwargs)

    def submit(self, fn: Callable, *args: Any, **kwargs: Any):
        return self._executor.submit(copy_telemetry_context(fn), *args, **kwargs)

    def __enter__(self):
        self._executor.__enter__()
        return self

    def __exit__(self, *exc_info):
        return self._executor.__exit__(*exc_info)
