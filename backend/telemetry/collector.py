"""TelemetryCollector — singleton background writer for telemetry events.

All public record_* methods are non-blocking (queue.put). A background
daemon thread drains the queue and batch-inserts into SQLite.

Telemetry errors are logged at DEBUG level and never propagated to callers.
"""

from __future__ import annotations

import json
import logging
import queue
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.telemetry.schema import init_db

logger = logging.getLogger(__name__)

_SENTINEL = object()

# Maximum JSON payload size before truncation (bytes)
_MAX_PAYLOAD_BYTES = 8192

# Batch flush settings
_FLUSH_INTERVAL_SEC = 0.5
_FLUSH_BATCH_SIZE = 50


def _uuid_short() -> str:
    return uuid.uuid4().hex[:12]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json(obj: Any, truncate: bool = False) -> str | None:
    """Serialize obj to JSON, handling Pydantic models, dataclasses, etc.

    Returns None if obj is None. Truncates large payloads if requested.
    """
    if obj is None:
        return None
    try:
        serialized = json.dumps(obj, default=_json_default)
    except (TypeError, ValueError):
        try:
            serialized = json.dumps(str(obj))
        except Exception:
            return None
    if truncate and len(serialized) > _MAX_PAYLOAD_BYTES:
        # Truncate and mark
        truncated = serialized[:_MAX_PAYLOAD_BYTES - 50]
        serialized = json.dumps({"_truncated": True, "_preview": truncated})
    return serialized


def _json_default(obj: Any) -> Any:
    """JSON serializer fallback for non-standard types."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


class TelemetryCollector:
    """Collects telemetry events and writes them to SQLite in a background thread.

    All record_* methods are non-blocking and thread-safe. They serialize the
    event and push it onto an internal queue. A background daemon thread
    batch-flushes the queue to the database.
    """

    def __init__(self, db_path: Path):
        self._conn = init_db(db_path)
        self._lock = threading.Lock()
        self._queue: queue.Queue = queue.Queue()
        self._closed = False
        self._writer = threading.Thread(
            target=self._writer_loop, daemon=True, name="telemetry-writer",
        )
        self._writer.start()

    # ── Public recording API ──

    def record_run_start(
        self, run_id: str, conversation_id: int | None,
        design_name: str, user_message: str | None,
    ) -> None:
        self._enqueue("run_start", {
            "id": run_id,
            "conversation_id": conversation_id,
            "design_name": design_name,
            "user_message": user_message,
            "started_at": _now_iso(),
        })

    def record_run_end(
        self, run_id: str, success: bool, duration_ms: int,
        error: str | None = None, final_response: str | None = None,
    ) -> None:
        self._enqueue("run_end", {
            "id": run_id,
            "success": success,
            "duration_ms": duration_ms,
            "error": error,
            "final_response": final_response,
            "ended_at": _now_iso(),
        })

    def record_module_trace(
        self, trace_id: str, run_id: str | None,
        parent_trace_id: str | None,
        module_class: str, signature_name: str | None,
        inputs: Any, outputs: Any, reasoning: str | None,
        duration_ms: int, success: bool, error: str | None = None,
    ) -> None:
        self._enqueue("module_trace", {
            "id": trace_id,
            "run_id": run_id,
            "parent_trace_id": parent_trace_id,
            "module_class": module_class,
            "signature_name": signature_name,
            "inputs": _safe_json(inputs, truncate=True),
            "outputs": _safe_json(outputs, truncate=True),
            "reasoning": reasoning,
            "started_at": _now_iso(),
            "duration_ms": duration_ms,
            "success": 1 if success else 0,
            "error": error,
        })

    def record_tool_call(
        self, call_id: str, run_id: str | None,
        module_trace_id: str | None,
        tool_name: str, arguments: Any, result: Any,
        duration_ms: int, success: bool, error: str | None = None,
    ) -> None:
        self._enqueue("tool_call", {
            "id": call_id,
            "run_id": run_id,
            "module_trace_id": module_trace_id,
            "tool_name": tool_name,
            "arguments": _safe_json(arguments, truncate=True),
            "result": _safe_json(result, truncate=True),
            "started_at": _now_iso(),
            "duration_ms": duration_ms,
            "success": 1 if success else 0,
            "error": error,
        })

    def record_workflow_trace(
        self, trace_id: str, run_id: str | None,
        workflow_name: str, outcome_id: int | None,
        outcome_description: str | None, params: Any,
        result_data: Any, summary: str | None,
        duration_ms: int, success: bool, error: str | None = None,
    ) -> None:
        self._enqueue("workflow_trace", {
            "id": trace_id,
            "run_id": run_id,
            "workflow_name": workflow_name,
            "outcome_id": outcome_id,
            "outcome_description": outcome_description,
            "params": _safe_json(params, truncate=True),
            "result_data": _safe_json(result_data, truncate=True),
            "summary": summary,
            "started_at": _now_iso(),
            "duration_ms": duration_ms,
            "success": 1 if success else 0,
            "error": error,
        })

    def record_llm_call(
        self, run_id: str | None, module_trace_id: str | None,
        model: str | None, tokens_in: int | None,
        tokens_out: int | None, latency_ms: int | None,
        cost_usd: float | None,
    ) -> None:
        self._enqueue("llm_call", {
            "id": _uuid_short(),
            "run_id": run_id,
            "module_trace_id": module_trace_id,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "called_at": _now_iso(),
        })

    def record_signal(
        self, signal_type: str, run_id: str | None = None,
        conversation_id: int | None = None, data: Any = None,
    ) -> None:
        self._enqueue("user_signal", {
            "id": _uuid_short(),
            "run_id": run_id,
            "conversation_id": conversation_id,
            "signal_type": signal_type,
            "data": _safe_json(data),
            "created_at": _now_iso(),
        })

    def compact(self, retention_days: int = 90) -> None:
        """Delete telemetry older than retention_days and vacuum."""
        try:
            cutoff = datetime.now(timezone.utc).isoformat()
            # Approximate cutoff by subtracting days from current ISO timestamp
            from datetime import timedelta
            cutoff = (
                datetime.now(timezone.utc) - timedelta(days=retention_days)
            ).isoformat()
            with self._lock:
                for table in [
                    "user_signals", "llm_calls", "tool_calls",
                    "module_traces", "workflow_traces", "runs",
                ]:
                    ts_col = "created_at" if table == "user_signals" else (
                        "called_at" if table == "llm_calls" else "started_at"
                    )
                    self._conn.execute(
                        f"DELETE FROM {table} WHERE {ts_col} < ?",  # noqa: S608
                        (cutoff,),
                    )
                self._conn.commit()
                self._conn.execute("VACUUM")
            logger.info("Telemetry compacted (retention=%d days)", retention_days)
        except Exception:
            logger.debug("Telemetry compaction failed", exc_info=True)

    def shutdown(self) -> None:
        """Drain remaining events and close the database connection."""
        if self._closed:
            return
        self._closed = True
        self._queue.put(_SENTINEL)
        self._writer.join(timeout=5.0)
        try:
            self._conn.close()
        except Exception:
            pass

    # ── Internal ──

    def _enqueue(self, event_type: str, data: dict) -> None:
        """Push an event onto the queue. Never raises."""
        if self._closed:
            return
        try:
            self._queue.put_nowait((event_type, data))
        except Exception:
            logger.debug("Failed to enqueue telemetry event", exc_info=True)

    def _writer_loop(self) -> None:
        """Background thread: batch-drain queue and write to SQLite."""
        batch: list[tuple[str, dict]] = []
        last_flush = time.monotonic()

        while True:
            try:
                item = self._queue.get(timeout=_FLUSH_INTERVAL_SEC)
            except queue.Empty:
                item = None

            if item is _SENTINEL:
                # Final flush
                if batch:
                    self._flush(batch)
                return

            if item is not None:
                batch.append(item)

            elapsed = time.monotonic() - last_flush
            if len(batch) >= _FLUSH_BATCH_SIZE or (batch and elapsed >= _FLUSH_INTERVAL_SEC):
                self._flush(batch)
                batch = []
                last_flush = time.monotonic()

    def _flush(self, batch: list[tuple[str, dict]]) -> None:
        """Write a batch of events to the database."""
        try:
            with self._lock:
                for event_type, data in batch:
                    self._write_event(event_type, data)
                self._conn.commit()
        except Exception:
            logger.debug("Telemetry flush failed", exc_info=True)

    def _write_event(self, event_type: str, data: dict) -> None:
        """Insert a single event into the appropriate table."""
        if event_type == "run_start":
            self._conn.execute(
                "INSERT INTO runs (id, conversation_id, design_name, user_message, started_at, success) "
                "VALUES (:id, :conversation_id, :design_name, :user_message, :started_at, 1)",
                data,
            )
        elif event_type == "run_end":
            self._conn.execute(
                "UPDATE runs SET success=:success, duration_ms=:duration_ms, "
                "error=:error, final_response=:final_response, ended_at=:ended_at "
                "WHERE id=:id",
                data,
            )
        elif event_type == "module_trace":
            self._conn.execute(
                "INSERT INTO module_traces "
                "(id, run_id, parent_trace_id, module_class, signature_name, "
                "inputs, outputs, reasoning, started_at, duration_ms, success, error) "
                "VALUES (:id, :run_id, :parent_trace_id, :module_class, :signature_name, "
                ":inputs, :outputs, :reasoning, :started_at, :duration_ms, :success, :error)",
                data,
            )
        elif event_type == "tool_call":
            self._conn.execute(
                "INSERT INTO tool_calls "
                "(id, run_id, module_trace_id, tool_name, arguments, result, "
                "started_at, duration_ms, success, error) "
                "VALUES (:id, :run_id, :module_trace_id, :tool_name, :arguments, "
                ":result, :started_at, :duration_ms, :success, :error)",
                data,
            )
        elif event_type == "workflow_trace":
            self._conn.execute(
                "INSERT INTO workflow_traces "
                "(id, run_id, workflow_name, outcome_id, outcome_description, "
                "params, result_data, summary, started_at, duration_ms, success, error) "
                "VALUES (:id, :run_id, :workflow_name, :outcome_id, :outcome_description, "
                ":params, :result_data, :summary, :started_at, :duration_ms, :success, :error)",
                data,
            )
        elif event_type == "llm_call":
            self._conn.execute(
                "INSERT INTO llm_calls "
                "(id, run_id, module_trace_id, model, tokens_in, tokens_out, "
                "latency_ms, cost_usd, called_at) "
                "VALUES (:id, :run_id, :module_trace_id, :model, :tokens_in, "
                ":tokens_out, :latency_ms, :cost_usd, :called_at)",
                data,
            )
        elif event_type == "user_signal":
            self._conn.execute(
                "INSERT INTO user_signals "
                "(id, run_id, conversation_id, signal_type, data, created_at) "
                "VALUES (:id, :run_id, :conversation_id, :signal_type, :data, :created_at)",
                data,
            )


# ── Module-level singleton ──

_collector: TelemetryCollector | None = None


def init_collector(db_path: Path) -> TelemetryCollector:
    """Initialize the global telemetry collector. Call once at app startup."""
    global _collector
    if _collector is not None:
        return _collector
    _collector = TelemetryCollector(db_path)
    return _collector


def get_collector() -> TelemetryCollector | None:
    """Return the global collector, or None if telemetry is disabled."""
    return _collector


def shutdown_collector() -> None:
    """Shut down the global collector. Call on app exit."""
    global _collector
    if _collector is not None:
        _collector.shutdown()
        _collector = None
