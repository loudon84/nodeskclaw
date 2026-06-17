"""Tests for Hermes Insight collectors and service."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.hermes_external.insight.profile_runtime_collector import ProfileRuntimeCollector
from app.services.hermes_external.insight.safe_path import resolve_insight_profile_paths
from app.services.hermes_external.insight.usage_collector import (
    _collect_from_state_db,
    _collect_from_webui_index,
    aggregate_profile_usages,
    collect_profile_usage,
    insight_cutoff,
)


def _prepare_host_data_dir(tmp_path: Path) -> Path:
    host_data_dir = tmp_path / "data" / "hermes"
    host_data_dir.mkdir(parents=True)
    (host_data_dir / ".env").write_text("API_SERVER_ENABLED=true\n", encoding="utf-8")
    (host_data_dir / "config.yaml").write_text("models: {}\n", encoding="utf-8")
    (host_data_dir / "SOUL.md").write_text("You are helpful.\n", encoding="utf-8")
    return host_data_dir


def _create_state_db(db_path: Path, *, include_cost: bool = True) -> None:
    conn = sqlite3.connect(db_path)
    columns = [
        "id TEXT",
        "model TEXT",
        "message_count INTEGER",
        "input_tokens INTEGER",
        "output_tokens INTEGER",
        "cache_read_tokens INTEGER",
        "cache_write_tokens INTEGER",
        "started_at TEXT",
        "ended_at TEXT",
        "source TEXT",
        "platform TEXT",
    ]
    if include_cost:
        columns.append("estimated_cost_usd REAL")
    conn.execute(f"CREATE TABLE sessions ({', '.join(columns)})")
    now = datetime.now(UTC).isoformat()
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    conn.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
        + (", ?" if include_cost else "")
        + ")",
        (
            "sess-1",
            "doubao/seed-2-0-pro",
            10,
            100,
            50,
            0,
            0,
            now,
            now,
            "cli",
            "web",
            *([0.12] if include_cost else []),
        ),
    )
    conn.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
        + (", ?" if include_cost else "")
        + ")",
        (
            "sess-old",
            "old-model",
            1,
            1,
            1,
            0,
            0,
            old,
            old,
            "cli",
            "web",
            *([0.01] if include_cost else []),
        ),
    )
    conn.commit()
    conn.close()


def test_resolve_insight_profile_paths(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    paths = resolve_insight_profile_paths(host_data_dir, "default")
    assert paths.state_db_path == host_data_dir / "state.db"
    assert paths.webui_index_path == host_data_dir / "webui" / "sessions" / "_index.json"


def test_collect_profile_usage_from_state_db(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    _create_state_db(host_data_dir / "state.db")
    result = collect_profile_usage(host_data_dir, "default")
    assert result.usage.total_sessions == 1
    assert result.usage.total_messages == 10
    assert result.usage.total_input_tokens == 100
    assert result.usage.total_output_tokens == 50
    assert result.usage.total_cost == pytest.approx(0.12)
    assert len(result.daily_tokens) == 30


def test_collect_profile_usage_state_db_missing_warning(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    result = collect_profile_usage(host_data_dir, "default")
    codes = [w.code for w in result.warnings]
    assert "STATE_DB_NOT_FOUND" in codes
    assert result.usage.total_sessions == 0


def test_collect_profile_usage_webui_index_fallback(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    index_path = host_data_dir / "webui" / "sessions" / "_index.json"
    index_path.parent.mkdir(parents=True)
    now = datetime.now(UTC).isoformat()
    payload = [
        {
            "session_id": "web-1",
            "model": "gpt-test",
            "message_count": 3,
            "input_tokens": 30,
            "output_tokens": 10,
            "estimated_cost": 0.05,
            "updated_at": now,
        }
    ]
    index_path.write_text(json.dumps(payload), encoding="utf-8")
    result = collect_profile_usage(host_data_dir, "default")
    assert result.usage.total_sessions == 1
    assert result.usage.total_messages == 3


def test_dedupe_prefers_state_db(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    _create_state_db(host_data_dir / "state.db")
    index_path = host_data_dir / "webui" / "sessions" / "_index.json"
    index_path.parent.mkdir(parents=True)
    now = datetime.now(UTC).isoformat()
    payload = [
        {
            "session_id": "sess-1",
            "model": "duplicate-model",
            "message_count": 99,
            "input_tokens": 999,
            "output_tokens": 999,
            "estimated_cost": 9.99,
            "updated_at": now,
        }
    ]
    index_path.write_text(json.dumps(payload), encoding="utf-8")
    paths = resolve_insight_profile_paths(host_data_dir, "default")
    cutoff = insight_cutoff()
    state_records, _ = _collect_from_state_db(paths, cutoff, cutoff.isoformat())
    index_records, _ = _collect_from_webui_index(paths, cutoff)
    assert len(state_records) == 1
    assert len(index_records) == 1
    assert state_records[0].session_id == index_records[0].session_id
    result = collect_profile_usage(host_data_dir, "default")
    assert result.usage.total_sessions == 1
    assert result.usage.total_messages == 10


def test_aggregate_profile_usages(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    writer = host_data_dir / "profiles" / "writer"
    writer.mkdir(parents=True)
    (writer / ".env").write_text("API_SERVER_ENABLED=true\n", encoding="utf-8")
    (writer / "config.yaml").write_text("models: {}\n", encoding="utf-8")
    (writer / "SOUL.md").write_text("writer\n", encoding="utf-8")
    _create_state_db(host_data_dir / "state.db")
    _create_state_db(writer / "state.db")

    default_result = collect_profile_usage(host_data_dir, "default")
    writer_result = collect_profile_usage(host_data_dir, "writer")
    usage, daily, models, breakdown, _ = aggregate_profile_usages(
        [default_result, writer_result],
        scope_profile="all",
    )
    assert usage.total_sessions == 2
    assert len(daily) == 30
    assert len(models) >= 1
    assert breakdown.input_tokens == default_result.usage.total_input_tokens + writer_result.usage.total_input_tokens


def test_profile_runtime_configured(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    collector = ProfileRuntimeCollector()
    runtime = collector.collect(host_data_dir, "default")
    assert runtime.status in {"configured", "idle", "unknown", "running"}
    assert runtime.config_exists is True
    assert runtime.state_db_exists is False


@pytest.mark.asyncio
async def test_container_health_collector_stats_unavailable():
    from app.services.hermes_external.insight.container_health_collector import ContainerHealthCollector

    collector = ContainerHealthCollector()
    with patch.object(
        collector._inspect_service,
        "inspect",
        new=AsyncMock(
            return_value=type(
                "R",
                (),
                {
                    "docker_status": "running",
                    "docker_health": "healthy",
                    "inspect_data": {"NetworkSettings": {"Ports": {}}},
                    "last_error": None,
                },
            )()
        ),
    ):
        with patch(
            "app.services.hermes_external.insight.container_health_collector.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=type("P", (), {"communicate": AsyncMock(return_value=(b"", b"fail")), "returncode": 1})()),
        ):
            info = await collector.collect(
                container_name="hermes-test",
                host_data_dir=Path("/tmp"),
            )
    assert info.docker_status == "running"
    assert any(w.code == "DOCKER_STATS_UNAVAILABLE" for w in info.warnings)


def test_insight_cutoff_is_30_days():
    cutoff = insight_cutoff()
    delta = datetime.now(UTC) - cutoff
    assert 29 <= delta.days <= 30
