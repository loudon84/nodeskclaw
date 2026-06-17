"""Hermes Insight orchestration service."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.exceptions import NotFoundError
from app.models.instance import Instance
from app.schemas.hermes_skill.hermes_insight import (
    ContainerRuntimeSchema,
    DailyTokenItemSchema,
    InsightResponseSchema,
    InsightWarningSchema,
    ModelUsageItemSchema,
    ProfileInsightItemSchema,
    ProfileRuntimeDetailSchema,
    TokenBreakdownSchema,
    UsageSummarySchema,
)
from app.services.hermes_external import profile_service
from app.services.hermes_external.profile_service import ProfileListContext
from app.services.hermes_external.insight.constants import (
    CACHE_TTL_PROFILE_INSIGHT_SECONDS,
    INSIGHT_WINDOW_DAYS,
)
from app.services.hermes_external.insight.container_health_collector import ContainerHealthCollector
from app.services.hermes_external.insight.profile_runtime_collector import ProfileRuntimeCollector
from app.services.hermes_external.insight.usage_collector import (
    ProfileUsageResult,
    aggregate_profile_usages,
    collect_profile_usage,
)


@dataclass
class _CacheEntry:
    expires_at: float
    payload: InsightResponseSchema


class HermesInsightService:
    def __init__(self) -> None:
        self._container_collector = ContainerHealthCollector()
        self._runtime_collector = ProfileRuntimeCollector()
        self._cache: dict[str, _CacheEntry] = {}

    async def get_insight(
        self,
        *,
        agent_profile_name: str,
        host_data_dir: Path,
        record: Any,
        instance: Instance | None,
        profile: str = "all",
        refresh: bool = False,
        ignore_days_param: bool = False,
    ) -> InsightResponseSchema:
        cache_key = f"{agent_profile_name}:{profile}:{refresh}"
        if not refresh:
            cached = self._cache.get(cache_key)
            if cached and cached.expires_at > time.time():
                return cached.payload

        profile_names = self._list_profile_names(host_data_dir, record, instance)
        if profile != "all":
            if profile not in profile_names:
                raise NotFoundError(
                    f"Profile not found in instance {agent_profile_name}: {profile}",
                    "errors.hermes.profile_not_found",
                )
            target_profiles = [profile]
        else:
            target_profiles = profile_names

        warnings: list[InsightWarningSchema] = []
        if ignore_days_param:
            warnings.append(
                InsightWarningSchema(
                    code="DAYS_PARAM_IGNORED",
                    message="days parameter is not supported; using fixed 30-day window",
                )
            )

        container_schema, container_warnings = await self._collect_container(record, host_data_dir)
        warnings.extend(_map_warnings(container_warnings))

        profile_items: list[ProfileInsightItemSchema] = []
        usage_results: list[ProfileUsageResult] = []

        for name in target_profiles:
            runtime = self._runtime_collector.collect(host_data_dir, name)
            usage_result = collect_profile_usage(host_data_dir, name)
            usage_results.append(usage_result)
            profile_items.append(
                ProfileInsightItemSchema(
                    profile_name=name,
                    runtime=_runtime_to_schema(runtime),
                    usage=_usage_to_schema(usage_result.usage),
                )
            )
            warnings.extend(_map_warnings(usage_result.warnings))

        if profile == "all":
            usage, daily_tokens, models, breakdown, agg_warnings = aggregate_profile_usages(
                usage_results,
                scope_profile="all",
            )
            warnings.extend(_map_warnings(agg_warnings))
            response = InsightResponseSchema(
                scope="instance",
                instance_id=agent_profile_name,
                profile_name="all",
                period_days=INSIGHT_WINDOW_DAYS,
                generated_at=datetime.now(UTC).isoformat(),
                container=container_schema,
                profiles=profile_items,
                usage=_usage_to_schema(usage),
                daily_tokens=[_daily_to_schema(item) for item in daily_tokens],
                models=[_model_to_schema(item) for item in models],
                token_breakdown=_breakdown_to_schema(breakdown),
                warnings=warnings,
            )
        else:
            single = usage_results[0]
            response = InsightResponseSchema(
                scope="profile",
                instance_id=agent_profile_name,
                profile_name=profile,
                period_days=INSIGHT_WINDOW_DAYS,
                generated_at=datetime.now(UTC).isoformat(),
                container=container_schema,
                profile=profile_items[0] if profile_items else None,
                usage=_usage_to_schema(single.usage),
                daily_tokens=[_daily_to_schema(item) for item in single.daily_tokens],
                models=[_model_to_schema(item) for item in single.models],
                token_breakdown=_breakdown_to_schema(single.token_breakdown),
                warnings=warnings,
            )

        self._cache[cache_key] = _CacheEntry(
            expires_at=time.time() + CACHE_TTL_PROFILE_INSIGHT_SECONDS,
            payload=response,
        )
        return response

    def _list_profile_names(self, host_data_dir: Path, record: Any, instance: Instance | None) -> list[str]:
        if instance is not None:
            data = profile_service.list_profiles(instance)
        else:
            ctx = ProfileListContext(host_data_dir=host_data_dir)
            if getattr(record, "instance_dir", None):
                ctx.instance_dir = Path(record.instance_dir)
            if getattr(record, "profile_name", None):
                ctx.agent_profile_name = record.profile_name
            data = profile_service.list_profiles_for_context(ctx)
        return [item.profile for item in data.items]

    async def _collect_container(self, record: Any, host_data_dir: Path) -> tuple[ContainerRuntimeSchema, list]:
        container_name = getattr(record, "container_name", "") or ""
        gateway_port = getattr(record, "gateway_port", None)
        webui_port = getattr(record, "webui_port", None)
        info = await self._container_collector.collect(
            container_name=container_name,
            host_data_dir=host_data_dir,
            gateway_port=gateway_port,
            webui_port=webui_port,
        )
        schema = ContainerRuntimeSchema(
            container_name=info.container_name,
            docker_status=info.docker_status,
            health=info.health,
            cpu_percent=info.cpu_percent,
            memory_used_bytes=info.memory_used_bytes,
            memory_limit_bytes=info.memory_limit_bytes,
            memory_percent=info.memory_percent,
            disk_used_bytes=info.disk_used_bytes,
            disk_total_bytes=info.disk_total_bytes,
            disk_percent=info.disk_percent,
            ports=info.ports,
            last_probe_at=info.last_probe_at,
        )
        return schema, info.warnings


def _runtime_to_schema(runtime) -> ProfileRuntimeDetailSchema:
    return ProfileRuntimeDetailSchema(
        status=runtime.status,
        api_server_enabled=runtime.api_server_enabled,
        api_server_port=runtime.api_server_port,
        webui_port=runtime.webui_port,
        state_db_exists=runtime.state_db_exists,
        config_exists=runtime.config_exists,
        webui_index_exists=runtime.webui_index_exists,
        last_state_write_at=runtime.last_state_write_at,
        last_session_at=runtime.last_session_at,
    )


def _usage_to_schema(usage) -> UsageSummarySchema:
    return UsageSummarySchema(
        total_sessions=usage.total_sessions,
        total_messages=usage.total_messages,
        total_input_tokens=usage.total_input_tokens,
        total_output_tokens=usage.total_output_tokens,
        total_tokens=usage.total_tokens,
        total_cost=round(usage.total_cost, 4),
    )


def _daily_to_schema(item) -> DailyTokenItemSchema:
    return DailyTokenItemSchema(
        date=item.date,
        profile_name=item.profile_name,
        sessions=item.sessions,
        messages=item.messages,
        input_tokens=item.input_tokens,
        output_tokens=item.output_tokens,
        total_tokens=item.total_tokens,
        cost=round(item.cost, 4),
    )


def _model_to_schema(item) -> ModelUsageItemSchema:
    return ModelUsageItemSchema(
        profile_name=item.profile_name,
        model=item.model,
        sessions=item.sessions,
        messages=item.messages,
        input_tokens=item.input_tokens,
        output_tokens=item.output_tokens,
        total_tokens=item.total_tokens,
        cost=round(item.cost, 4),
        session_share=item.session_share,
        token_share=item.token_share,
        cost_share=item.cost_share,
    )


def _breakdown_to_schema(breakdown) -> TokenBreakdownSchema:
    return TokenBreakdownSchema(
        input_tokens=breakdown.input_tokens,
        output_tokens=breakdown.output_tokens,
        cache_read_tokens=breakdown.cache_read_tokens,
        cache_write_tokens=breakdown.cache_write_tokens,
    )


def _map_warnings(warnings) -> list[InsightWarningSchema]:
    return [
        InsightWarningSchema(
            code=w.code,
            message=w.message,
            profile_name=getattr(w, "profile_name", None),
        )
        for w in warnings
    ]
