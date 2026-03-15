"""TracedModule — mixin for DSPy modules that captures telemetry.

Add as a base class alongside dspy.Module to automatically record
inputs, outputs, reasoning, and timing for every module invocation:

    class OutcomePlanner(TracedModule, dspy.Module):
        ...

The mixin wraps __call__ (which DSPy routes through forward()) to
capture data without modifying the module's logic.
"""

from __future__ import annotations

import logging
import time

from backend.telemetry.collector import _uuid_short, get_collector
from backend.telemetry.context import current_run_id, current_trace_id

logger = logging.getLogger(__name__)


class TracedModule:
    """Mixin that adds telemetry tracing to a dspy.Module subclass.

    When the collector is not initialized (telemetry disabled), this is
    a transparent no-op — the overhead is a single ``get_collector()``
    call returning None.
    """

    def __call__(self, *args, **kwargs):
        collector = get_collector()
        if collector is None:
            return super().__call__(*args, **kwargs)

        run_id = current_run_id.get()
        parent_id = current_trace_id.get()
        trace_id = _uuid_short()
        token = current_trace_id.set(trace_id)

        t0 = time.monotonic()
        try:
            result = super().__call__(*args, **kwargs)
            duration_ms = int((time.monotonic() - t0) * 1000)
            try:
                collector.record_module_trace(
                    trace_id=trace_id,
                    run_id=run_id,
                    parent_trace_id=parent_id,
                    module_class=type(self).__name__,
                    signature_name=_get_signature_name(self),
                    inputs=_serialize_kwargs(kwargs),
                    outputs=_extract_outputs(result),
                    reasoning=_extract_reasoning(result),
                    duration_ms=duration_ms,
                    success=True,
                )
            except Exception:
                logger.debug("Telemetry: failed to record module trace", exc_info=True)
            return result
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            try:
                collector.record_module_trace(
                    trace_id=trace_id,
                    run_id=run_id,
                    parent_trace_id=parent_id,
                    module_class=type(self).__name__,
                    signature_name=_get_signature_name(self),
                    inputs=_serialize_kwargs(kwargs),
                    outputs=None,
                    reasoning=None,
                    duration_ms=duration_ms,
                    success=False,
                    error=str(exc),
                )
            except Exception:
                logger.debug("Telemetry: failed to record module error trace", exc_info=True)
            raise
        finally:
            current_trace_id.reset(token)


def _get_signature_name(module: object) -> str | None:
    """Try to discover the DSPy Signature class name for a module.

    Looks at the module's predictors (if any) to find the signature.
    Falls back to None if introspection fails.
    """
    try:
        predictors = getattr(module, "predictors", None)
        if callable(predictors):
            preds = predictors()
            if preds:
                sig = getattr(preds[0], "signature", None)
                if sig is not None:
                    # DSPy wraps signatures in StringSignature; get the
                    # original name from __qualname__ or __name__
                    name = getattr(sig, "__qualname__", None) or type(sig).__name__
                    # StringSignature.__qualname__ is not helpful; check
                    # if the module stored the original signature class
                    if name == "SignatureMeta" or "StringSignature" in name:
                        return None
                    return name
    except Exception:
        pass
    return None


def _serialize_kwargs(kwargs: dict) -> dict:
    """Convert kwargs to a JSON-safe dict, handling common types."""
    result = {}
    for k, v in kwargs.items():
        if isinstance(v, str):
            result[k] = v
        elif isinstance(v, (int, float, bool, type(None))):
            result[k] = v
        elif isinstance(v, (list, dict)):
            result[k] = v
        elif hasattr(v, "model_dump"):
            result[k] = v.model_dump()
        elif hasattr(v, "toDict"):
            result[k] = v.toDict()
        else:
            result[k] = str(v)
    return result


def _extract_outputs(result: object) -> dict | None:
    """Extract output fields from a DSPy Prediction or similar result."""
    if result is None:
        return None
    try:
        if hasattr(result, "toDict"):
            d = result.toDict()
            # Remove 'reasoning' / 'rationale' from outputs — captured separately
            d.pop("reasoning", None)
            d.pop("rationale", None)
            return d
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if isinstance(result, dict):
            return result
        return {"_raw": str(result)}
    except Exception:
        return None


def _extract_reasoning(result: object) -> str | None:
    """Extract chain-of-thought reasoning from a DSPy Prediction."""
    if result is None:
        return None
    try:
        # DSPy ChainOfThought adds 'reasoning' to the prediction
        reasoning = getattr(result, "reasoning", None)
        if reasoning:
            return str(reasoning)
        rationale = getattr(result, "rationale", None)
        if rationale:
            return str(rationale)
    except Exception:
        pass
    return None
