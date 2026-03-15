"""Telemetry database schema and initialization.

Creates and migrates the telemetry.db SQLite database used to store
agent traces, tool calls, workflow results, LLM metrics, and user signals.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

_SCHEMA_SQL = """
-- Schema metadata
CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Complete agent runs (one per user message -> response cycle)
CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    conversation_id INTEGER,
    design_name     TEXT NOT NULL,
    user_message    TEXT,
    final_response  TEXT,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    duration_ms     INTEGER,
    success         INTEGER NOT NULL DEFAULT 1,
    error           TEXT
);

-- DSPy module invocations (nested tree via parent_trace_id)
CREATE TABLE IF NOT EXISTS module_traces (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    parent_trace_id TEXT REFERENCES module_traces(id),
    module_class    TEXT NOT NULL,
    signature_name  TEXT,
    inputs          TEXT,
    outputs         TEXT,
    reasoning       TEXT,
    started_at      TEXT NOT NULL,
    duration_ms     INTEGER,
    success         INTEGER NOT NULL DEFAULT 1,
    error           TEXT
);

-- Tool invocations
CREATE TABLE IF NOT EXISTS tool_calls (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(id),
    module_trace_id TEXT REFERENCES module_traces(id),
    tool_name       TEXT NOT NULL,
    arguments       TEXT,
    result          TEXT,
    started_at      TEXT NOT NULL,
    duration_ms     INTEGER,
    success         INTEGER NOT NULL DEFAULT 1,
    error           TEXT
);

-- Workflow-level traces
CREATE TABLE IF NOT EXISTS workflow_traces (
    id                  TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL REFERENCES runs(id),
    workflow_name       TEXT NOT NULL,
    outcome_id          INTEGER,
    outcome_description TEXT,
    params              TEXT,
    result_data         TEXT,
    summary             TEXT,
    started_at          TEXT NOT NULL,
    duration_ms         INTEGER,
    success             INTEGER NOT NULL DEFAULT 1,
    error               TEXT
);

-- Raw LLM call metrics (from LiteLLM callback)
CREATE TABLE IF NOT EXISTS llm_calls (
    id              TEXT PRIMARY KEY,
    run_id          TEXT REFERENCES runs(id),
    module_trace_id TEXT REFERENCES module_traces(id),
    model           TEXT,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    latency_ms      INTEGER,
    cost_usd        REAL,
    called_at       TEXT NOT NULL
);

-- User signals (feedback, implicit actions)
CREATE TABLE IF NOT EXISTS user_signals (
    id              TEXT PRIMARY KEY,
    run_id          TEXT REFERENCES runs(id),
    conversation_id INTEGER,
    signal_type     TEXT NOT NULL,
    data            TEXT,
    created_at      TEXT NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_module_traces_run   ON module_traces(run_id);
CREATE INDEX IF NOT EXISTS idx_module_traces_class ON module_traces(module_class);
CREATE INDEX IF NOT EXISTS idx_tool_calls_run      ON tool_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_workflow_traces_run ON workflow_traces(run_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_run       ON llm_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_user_signals_run    ON user_signals(run_id);
CREATE INDEX IF NOT EXISTS idx_user_signals_type   ON user_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_runs_conversation   ON runs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_runs_design         ON runs(design_name);
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create or open the telemetry database and ensure schema is current.

    Returns a connection configured for WAL mode and foreign keys.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript(_SCHEMA_SQL)

    # Insert or update meta rows
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO _meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.execute(
        "INSERT OR IGNORE INTO _meta (key, value) VALUES ('created_at', ?)",
        (now,),
    )
    conn.commit()

    _migrate_db(conn)
    logger.info("Telemetry database initialized at %s", db_path)
    return conn


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Run any pending schema migrations.

    Currently a no-op since we're at schema_version 1. Future migrations
    will check the stored version and apply ALTER TABLE statements as needed.
    """
    row = conn.execute(
        "SELECT value FROM _meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        return
    stored_version = int(row["value"])
    if stored_version < SCHEMA_VERSION:
        logger.info(
            "Migrating telemetry DB from v%d to v%d",
            stored_version, SCHEMA_VERSION,
        )
        # Future migrations go here:
        # if stored_version < 2: _migrate_v1_to_v2(conn)
        conn.execute(
            "UPDATE _meta SET value = ? WHERE key = 'schema_version'",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
