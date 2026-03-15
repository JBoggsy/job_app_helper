"""Telemetry export utilities.

Provides functions to export telemetry data in various formats:
- Full SQLite copy (for complete data sharing)
- Anonymized SQLite copy (strips user content)
- DSPy Example format (for optimizer training data)
- JSONL format (for interoperability)
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Columns to strip in anonymized exports
_ANONYMIZE_COLUMNS = {
    "runs": ["user_message", "final_response"],
    "module_traces": ["inputs", "outputs", "reasoning"],
    "tool_calls": ["arguments", "result"],
    "workflow_traces": ["params", "result_data", "outcome_description"],
}


def export_full(source_db: Path, output_path: Path) -> Path:
    """Copy the telemetry database as-is.

    Returns the output path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_db), str(output_path))
    logger.info("Full telemetry export → %s", output_path)
    return output_path


def export_anonymized(source_db: Path, output_path: Path) -> Path:
    """Copy the telemetry database with user content stripped.

    Replaces sensitive text columns (user messages, tool arguments,
    LLM outputs) with NULL while preserving structural data (module
    names, timings, success/failure, token counts, signal types).

    Returns the output path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_db), str(output_path))

    conn = sqlite3.connect(str(output_path))
    try:
        for table, columns in _ANONYMIZE_COLUMNS.items():
            set_clause = ", ".join(f"{col} = NULL" for col in columns)
            conn.execute(f"UPDATE {table} SET {set_clause}")  # noqa: S608
        conn.execute(
            "UPDATE user_signals SET data = NULL "
            "WHERE signal_type NOT IN ('thumbs_up', 'thumbs_down')"
        )
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()

    logger.info("Anonymized telemetry export → %s", output_path)
    return output_path


def export_dspy_examples(
    source_db: Path,
    module_class: str,
    only_successful: bool = True,
) -> list[dict]:
    """Extract module traces as dicts suitable for creating dspy.Example objects.

    Each returned dict has 'inputs' and 'outputs' keys containing the
    JSON-decoded data from the module_traces table.

    Args:
        source_db: Path to the telemetry database.
        module_class: Name of the DSPy module class (e.g., "OutcomePlanner").
        only_successful: If True, only include traces where success=1.

    Returns:
        List of dicts with 'inputs', 'outputs', and 'reasoning' keys.
    """
    conn = sqlite3.connect(str(source_db))
    conn.row_factory = sqlite3.Row
    try:
        where = "WHERE module_class = ?"
        params: list = [module_class]
        if only_successful:
            where += " AND success = 1"

        rows = conn.execute(
            f"SELECT inputs, outputs, reasoning, duration_ms "  # noqa: S608
            f"FROM module_traces {where} ORDER BY started_at",
            params,
        ).fetchall()

        examples = []
        for row in rows:
            inputs = _safe_json_loads(row["inputs"])
            outputs = _safe_json_loads(row["outputs"])
            if inputs is None or outputs is None:
                continue
            examples.append({
                "inputs": inputs,
                "outputs": outputs,
                "reasoning": row["reasoning"],
                "duration_ms": row["duration_ms"],
            })

        logger.info(
            "Exported %d DSPy examples for module %s",
            len(examples), module_class,
        )
        return examples
    finally:
        conn.close()


def export_jsonl(source_db: Path, output_path: Path, table: str | None = None) -> Path:
    """Export telemetry table(s) as JSONL.

    Args:
        source_db: Path to the telemetry database.
        output_path: Output file path (or directory if table is None).
        table: Specific table to export. If None, exports all tables
               as separate files in output_path directory.

    Returns:
        The output path.
    """
    tables = [table] if table else [
        "runs", "module_traces", "tool_calls",
        "workflow_traces", "llm_calls", "user_signals",
    ]

    conn = sqlite3.connect(str(source_db))
    conn.row_factory = sqlite3.Row
    try:
        if table:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            _export_table_jsonl(conn, table, output_path)
        else:
            output_path.mkdir(parents=True, exist_ok=True)
            for t in tables:
                _export_table_jsonl(conn, t, output_path / f"{t}.jsonl")
    finally:
        conn.close()

    logger.info("JSONL export → %s", output_path)
    return output_path


def get_stats(source_db: Path) -> dict:
    """Return summary statistics for the telemetry database.

    Returns:
        Dict with table counts and database file size.
    """
    if not source_db.exists():
        return {"exists": False}

    conn = sqlite3.connect(str(source_db))
    try:
        stats = {"exists": True, "size_bytes": source_db.stat().st_size}
        for table in [
            "runs", "module_traces", "tool_calls",
            "workflow_traces", "llm_calls", "user_signals",
        ]:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            stats[table] = count
        return stats
    finally:
        conn.close()


# ── Internal ──

def _export_table_jsonl(conn: sqlite3.Connection, table: str, path: Path) -> None:
    """Write all rows of a table as JSONL."""
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(dict(row), default=str) + "\n")


def _safe_json_loads(s: str | None) -> dict | None:
    if s is None:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None
