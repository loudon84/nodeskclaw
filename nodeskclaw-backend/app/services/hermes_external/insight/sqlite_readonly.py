"""Read-only SQLite helpers for Hermes Insight."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.services.hermes_external.insight.constants import SQLITE_QUERY_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


@contextmanager
def open_readonly_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, timeout=SQLITE_QUERY_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except sqlite3.Error:
        return set()
    return {str(row[1]) for row in rows}


def fetch_sessions(
    conn: sqlite3.Connection,
    *,
    cutoff_iso: str,
    available_columns: set[str],
) -> list[dict[str, Any]]:
    if "sessions" not in _table_names(conn):
        return []

    select_parts: list[str] = []
    for col in (
        "id",
        "model",
        "message_count",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "estimated_cost_usd",
        "started_at",
        "ended_at",
        "source",
        "platform",
    ):
        if col in available_columns:
            select_parts.append(col)
        else:
            select_parts.append(f"NULL AS {col}")

    if not select_parts:
        return []

    time_filters: list[str] = []
    params: list[str] = []
    if "started_at" in available_columns:
        time_filters.append("started_at >= ?")
        params.append(cutoff_iso)
    if "ended_at" in available_columns:
        time_filters.append("ended_at >= ?")
        params.append(cutoff_iso)

    where_clause = ""
    if time_filters:
        where_clause = "WHERE " + " OR ".join(time_filters)

    sql = f"SELECT {', '.join(select_parts)} FROM sessions {where_clause}"
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error as exc:
        logger.warning("sqlite sessions query failed: %s", exc)
        return []

    return [dict(row) for row in rows]


def _table_names(conn: sqlite3.Connection) -> set[str]:
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    except sqlite3.Error:
        return set()
    return {str(row[0]) for row in rows}
