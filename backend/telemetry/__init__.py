"""Telemetry package for collecting DSPy optimization training data.

Passively collects agent traces, tool calls, workflow results, LLM metrics,
and user feedback during normal app usage. Data is stored in a separate
SQLite database (telemetry.db) for easy sharing and export.

Quick start:
    from backend.telemetry import init_collector, get_collector, shutdown_collector
    from backend.telemetry.context import telemetry_run
    from backend.telemetry.traced_module import TracedModule
"""

from backend.telemetry.collector import (
    get_collector,
    init_collector,
    shutdown_collector,
)

__all__ = [
    "init_collector",
    "get_collector",
    "shutdown_collector",
]
