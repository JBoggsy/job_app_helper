"""Telemetry decorators for workflow and agent tracing.

Provides decorators that can be applied manually or auto-applied via
__init_subclass__ to capture workflow execution data.
"""

from __future__ import annotations

import functools
import logging
import time

from backend.telemetry.collector import _uuid_short, get_collector
from backend.telemetry.context import current_run_id

logger = logging.getLogger(__name__)


def traced_workflow(fn):
    """Decorator for BaseWorkflow.run() methods.

    Captures workflow name, outcome, params, result, timing, and success
    status. Errors in telemetry recording are logged and swallowed.

    The decorated function gains a ``_traced = True`` attribute to
    prevent double-wrapping by __init_subclass__.
    """

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        collector = get_collector()
        if collector is None:
            return fn(self, *args, **kwargs)

        trace_id = _uuid_short()
        run_id = current_run_id.get()
        t0 = time.monotonic()

        try:
            result = fn(self, *args, **kwargs)
            duration_ms = int((time.monotonic() - t0) * 1000)
            try:
                collector.record_workflow_trace(
                    trace_id=trace_id,
                    run_id=run_id,
                    workflow_name=type(self).__name__,
                    outcome_id=getattr(self, "outcome_id", None),
                    outcome_description=getattr(self, "outcome_description", None),
                    params=getattr(self, "params", None),
                    result_data=result.data if result else None,
                    summary=result.summary if result else None,
                    duration_ms=duration_ms,
                    success=result.success if result else False,
                )
            except Exception:
                logger.debug("Telemetry: failed to record workflow trace", exc_info=True)
            return result
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            try:
                collector.record_workflow_trace(
                    trace_id=trace_id,
                    run_id=run_id,
                    workflow_name=type(self).__name__,
                    outcome_id=getattr(self, "outcome_id", None),
                    outcome_description=getattr(self, "outcome_description", None),
                    params=getattr(self, "params", None),
                    result_data=None,
                    summary=None,
                    duration_ms=duration_ms,
                    success=False,
                    error=str(exc),
                )
            except Exception:
                logger.debug("Telemetry: failed to record workflow error trace", exc_info=True)
            raise

    wrapper._traced = True
    return wrapper
