"""Usage statistics collector for Hermes Insight."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.hermes_external.insight.constants import INSIGHT_WINDOW_DAYS, WEBUI_INDEX_MAX_BYTES
from app.services.hermes_external.insight.safe_path import InsightProfilePaths, resolve_insight_profile_paths
from app.services.hermes_external.insight.sqlite_readonly import fetch_sessions, open_readonly_db, table_columns

logger = logging.getLogger(__name__)


@dataclass
class InsightWarning:
    code: str
    message: str
    profile_name: str | None = None


@dataclass
class SessionRecord:
    session_id: str
    profile_name: str
    source: str
    model: str
    message_count: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    estimated_cost: float
    event_date: str | None


@dataclass
class UsageSummary:
    total_sessions: int = 0
    total_messages: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class DailyTokenItem:
    date: str
    profile_name: str
    sessions: int = 0
    messages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


@dataclass
class ModelUsageItem:
    profile_name: str
    model: str
    sessions: int = 0
    messages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    session_share: float = 0.0
    token_share: float = 0.0
    cost_share: float = 0.0


@dataclass
class TokenBreakdown:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass
class ProfileUsageResult:
    profile_name: str
    usage: UsageSummary
    daily_tokens: list[DailyTokenItem] = field(default_factory=list)
    models: list[ModelUsageItem] = field(default_factory=list)
    token_breakdown: TokenBreakdown = field(default_factory=TokenBreakdown)
    warnings: list[InsightWarning] = field(default_factory=list)


def insight_cutoff() -> datetime:
    return datetime.now(UTC) - timedelta(days=INSIGHT_WINDOW_DAYS)


def collect_profile_usage(host_data_dir: Path, profile_name: str) -> ProfileUsageResult:
    paths = resolve_insight_profile_paths(host_data_dir, profile_name)
    warnings: list[InsightWarning] = []
    cutoff = insight_cutoff()
    cutoff_iso = cutoff.isoformat()

    state_records, state_warnings = _collect_from_state_db(paths, cutoff, cutoff_iso)
    warnings.extend(state_warnings)

    index_records, index_warnings = _collect_from_webui_index(paths, cutoff)
    warnings.extend(index_warnings)

    merged = _merge_records(profile_name, state_records, index_records)
    usage = _aggregate_usage(merged)
    daily = _aggregate_daily(merged, profile_name)
    models = _aggregate_models(merged, profile_name)
    breakdown = _aggregate_breakdown(merged)

    if not paths.state_db_path.is_file() and not merged:
        warnings.append(
            InsightWarning(
                code="STATE_DB_NOT_FOUND",
                message=f"state.db not found for profile {profile_name}",
                profile_name=profile_name,
            )
        )

    return ProfileUsageResult(
        profile_name=profile_name,
        usage=usage,
        daily_tokens=daily,
        models=models,
        token_breakdown=breakdown,
        warnings=warnings,
    )


def aggregate_profile_usages(results: list[ProfileUsageResult], *, scope_profile: str = "all") -> tuple[
    UsageSummary,
    list[DailyTokenItem],
    list[ModelUsageItem],
    TokenBreakdown,
    list[InsightWarning],
]:
    usage = UsageSummary()
    warnings: list[InsightWarning] = []

    for result in results:
        usage.total_sessions += result.usage.total_sessions
        usage.total_messages += result.usage.total_messages
        usage.total_input_tokens += result.usage.total_input_tokens
        usage.total_output_tokens += result.usage.total_output_tokens
        usage.total_cost += result.usage.total_cost
        warnings.extend(result.warnings)

    usage.total_tokens = usage.total_input_tokens + usage.total_output_tokens

    daily_map: dict[str, DailyTokenItem] = {}
    for result in results:
        for item in result.daily_tokens:
            key = item.date
            if key not in daily_map:
                daily_map[key] = DailyTokenItem(date=key, profile_name=scope_profile)
            agg = daily_map[key]
            agg.sessions += item.sessions
            agg.messages += item.messages
            agg.input_tokens += item.input_tokens
            agg.output_tokens += item.output_tokens
            agg.total_tokens += item.total_tokens
            agg.cost += item.cost

    daily_tokens = _fill_daily_range(daily_map, scope_profile)

    models: list[ModelUsageItem] = []
    for result in results:
        models.extend(result.models)
    models = _compute_model_shares(models)

    breakdown = TokenBreakdown()
    for result in results:
        breakdown.input_tokens += result.token_breakdown.input_tokens
        breakdown.output_tokens += result.token_breakdown.output_tokens
        breakdown.cache_read_tokens += result.token_breakdown.cache_read_tokens
        breakdown.cache_write_tokens += result.token_breakdown.cache_write_tokens

    return usage, daily_tokens, models, breakdown, warnings


def _collect_from_state_db(
    paths: InsightProfilePaths,
    cutoff: datetime,
    cutoff_iso: str,
) -> tuple[list[SessionRecord], list[InsightWarning]]:
    warnings: list[InsightWarning] = []
    if not paths.state_db_path.is_file():
        return [], warnings

    try:
        with open_readonly_db(paths.state_db_path) as conn:
            columns = table_columns(conn, "sessions")
            if not columns:
                warnings.append(
                    InsightWarning(
                        code="STATE_DB_SCHEMA_UNSUPPORTED",
                        message=f"sessions table missing in state.db for profile {paths.profile_name}",
                        profile_name=paths.profile_name,
                    )
                )
                return [], warnings
            rows = fetch_sessions(conn, cutoff_iso=cutoff_iso, available_columns=columns)
    except Exception as exc:
        logger.warning("state.db read failed for %s: %s", paths.profile_name, exc)
        warnings.append(
            InsightWarning(
                code="STATE_DB_READ_FAILED",
                message=f"Failed to read state.db for profile {paths.profile_name}",
                profile_name=paths.profile_name,
            )
        )
        return [], warnings

    records: list[SessionRecord] = []
    for row in rows:
        record = _row_to_session_record(paths.profile_name, "state_db", row)
        if record and _record_within_cutoff(record, cutoff):
            records.append(record)
    return records, warnings


def _collect_from_webui_index(
    paths: InsightProfilePaths,
    cutoff: datetime,
) -> tuple[list[SessionRecord], list[InsightWarning]]:
    warnings: list[InsightWarning] = []
    index_path = paths.webui_index_path
    if not index_path.is_file():
        warnings.append(
            InsightWarning(
                code="WEBUI_INDEX_NOT_FOUND",
                message=f"webui sessions index not found for profile {paths.profile_name}",
                profile_name=paths.profile_name,
            )
        )
        return [], warnings

    try:
        size = index_path.stat().st_size
        if size > WEBUI_INDEX_MAX_BYTES:
            warnings.append(
                InsightWarning(
                    code="WEBUI_INDEX_TOO_LARGE",
                    message=f"webui sessions index too large for profile {paths.profile_name}",
                    profile_name=paths.profile_name,
                )
            )
            return [], warnings
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("webui index read failed for %s: %s", paths.profile_name, exc)
        warnings.append(
            InsightWarning(
                code="WEBUI_INDEX_READ_FAILED",
                message=f"Failed to read webui sessions index for profile {paths.profile_name}",
                profile_name=paths.profile_name,
            )
        )
        return [], warnings

    entries = _normalize_index_entries(payload)
    records: list[SessionRecord] = []
    for entry in entries:
        record = _index_entry_to_session_record(paths.profile_name, entry, cutoff)
        if record:
            records.append(record)
    return records, warnings


def _normalize_index_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [e for e in payload if isinstance(e, dict)]
    if isinstance(payload, dict):
        sessions = payload.get("sessions")
        if isinstance(sessions, list):
            return [e for e in sessions if isinstance(e, dict)]
        return [v for v in payload.values() if isinstance(v, dict)]
    return []


def _merge_records(
    profile_name: str,
    state_records: list[SessionRecord],
    index_records: list[SessionRecord],
) -> list[SessionRecord]:
    merged: dict[str, SessionRecord] = {}
    for record in state_records:
        merged[_session_key(profile_name, record)] = record
    for record in index_records:
        key = _session_key(profile_name, record)
        if key not in merged:
            merged[key] = record
    return list(merged.values())


def _session_key(profile_name: str, record: SessionRecord) -> str:
    return f"{profile_name}:{record.session_id}"


def _row_to_session_record(profile_name: str, source: str, row: dict[str, Any]) -> SessionRecord | None:
    session_id = str(row.get("id") or "").strip()
    if not session_id:
        return None
    event_date = _parse_event_date(row.get("started_at") or row.get("ended_at"))
    return SessionRecord(
        session_id=session_id,
        profile_name=profile_name,
        source=source,
        model=str(row.get("model") or "unknown"),
        message_count=_to_int(row.get("message_count")),
        input_tokens=_to_int(row.get("input_tokens")),
        output_tokens=_to_int(row.get("output_tokens")),
        cache_read_tokens=_to_int(row.get("cache_read_tokens")),
        cache_write_tokens=_to_int(row.get("cache_write_tokens")),
        estimated_cost=_to_float(row.get("estimated_cost_usd")),
        event_date=event_date,
    )


def _index_entry_to_session_record(
    profile_name: str,
    entry: dict[str, Any],
    cutoff: datetime,
) -> SessionRecord | None:
    session_id = str(entry.get("session_id") or entry.get("id") or "").strip()
    if not session_id:
        return None
    event_dt = _parse_event_datetime(
        entry.get("updated_at") or entry.get("created_at") or entry.get("started_at")
    )
    if event_dt and event_dt < cutoff:
        return None
    event_date = event_dt.date().isoformat() if event_dt else None
    cost = entry.get("estimated_cost")
    if cost is None:
        cost = entry.get("estimated_cost_usd")
    return SessionRecord(
        session_id=session_id,
        profile_name=profile_name,
        source="webui_index",
        model=str(entry.get("model") or "unknown"),
        message_count=_to_int(entry.get("message_count")),
        input_tokens=_to_int(entry.get("input_tokens")),
        output_tokens=_to_int(entry.get("output_tokens")),
        cache_read_tokens=_to_int(entry.get("cache_read_tokens")),
        cache_write_tokens=_to_int(entry.get("cache_write_tokens")),
        estimated_cost=_to_float(cost),
        event_date=event_date,
    )


def _aggregate_usage(records: list[SessionRecord]) -> UsageSummary:
    usage = UsageSummary(total_sessions=len(records))
    for record in records:
        usage.total_messages += record.message_count
        usage.total_input_tokens += record.input_tokens
        usage.total_output_tokens += record.output_tokens
        usage.total_cost += record.estimated_cost
    usage.total_tokens = usage.total_input_tokens + usage.total_output_tokens
    return usage


def _aggregate_daily(records: list[SessionRecord], profile_name: str) -> list[DailyTokenItem]:
    daily_map: dict[str, DailyTokenItem] = {}
    for record in records:
        date = record.event_date or datetime.now(UTC).date().isoformat()
        if date not in daily_map:
            daily_map[date] = DailyTokenItem(date=date, profile_name=profile_name)
        item = daily_map[date]
        item.sessions += 1
        item.messages += record.message_count
        item.input_tokens += record.input_tokens
        item.output_tokens += record.output_tokens
        item.total_tokens += record.input_tokens + record.output_tokens
        item.cost += record.estimated_cost
    return _fill_daily_range(daily_map, profile_name)


def _fill_daily_range(daily_map: dict[str, DailyTokenItem], profile_name: str) -> list[DailyTokenItem]:
    today = datetime.now(UTC).date()
    result: list[DailyTokenItem] = []
    for offset in range(INSIGHT_WINDOW_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        if key in daily_map:
            result.append(daily_map[key])
        else:
            result.append(DailyTokenItem(date=key, profile_name=profile_name))
    return result


def _aggregate_models(records: list[SessionRecord], profile_name: str) -> list[ModelUsageItem]:
    model_map: dict[str, ModelUsageItem] = {}
    for record in records:
        key = record.model
        if key not in model_map:
            model_map[key] = ModelUsageItem(profile_name=profile_name, model=key)
        item = model_map[key]
        item.sessions += 1
        item.messages += record.message_count
        item.input_tokens += record.input_tokens
        item.output_tokens += record.output_tokens
        item.total_tokens += record.input_tokens + record.output_tokens
        item.cost += record.estimated_cost
    return _compute_model_shares(list(model_map.values()))


def _compute_model_shares(models: list[ModelUsageItem]) -> list[ModelUsageItem]:
    total_sessions = sum(m.sessions for m in models) or 1
    total_tokens = sum(m.total_tokens for m in models) or 1
    total_cost = sum(m.cost for m in models) or 1.0
    for item in models:
        item.session_share = round(item.sessions / total_sessions * 100, 1)
        item.token_share = round(item.total_tokens / total_tokens * 100, 1)
        item.cost_share = round(item.cost / total_cost * 100, 1)
    return sorted(models, key=lambda m: m.total_tokens, reverse=True)


def _aggregate_breakdown(records: list[SessionRecord]) -> TokenBreakdown:
    breakdown = TokenBreakdown()
    for record in records:
        breakdown.input_tokens += record.input_tokens
        breakdown.output_tokens += record.output_tokens
        breakdown.cache_read_tokens += record.cache_read_tokens
        breakdown.cache_write_tokens += record.cache_write_tokens
    return breakdown


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse_event_date(value: Any) -> str | None:
    dt = _parse_event_datetime(value)
    return dt.date().isoformat() if dt else None


def _parse_event_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _record_within_cutoff(record: SessionRecord, cutoff: datetime) -> bool:
    if not record.event_date:
        return True
    try:
        day = datetime.fromisoformat(record.event_date).date()
    except ValueError:
        return True
    return day >= cutoff.date()
