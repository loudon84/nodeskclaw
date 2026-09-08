from __future__ import annotations

# @lat: [[architecture/skill-agent#Execution Observability Trace And Metrics]]
import logging
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

TRACE_ID_MAX_LEN = 64
_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

ALLOWED_TRACE_ATTRS = frozenset(
    {
        "run_id",
        "attempt_id",
        "session_id",
        "skill_release_id",
        "step_id",
        "generation",
        "delivery_generation",
        "edge_node_id",
        "request_trace_id",
        "engine",
        "stage",
        "outcome",
        "error_code",
    }
)

ALLOWED_LABEL_KEYS = frozenset({"role", "outcome", "engine", "kind", "stage"})

_SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "api_key",
    "authorization",
    "auth_token",
    "prompt",
    "credential",
    "private_key",
)

METRIC_DEFINITIONS: dict[str, dict[str, Any]] = {
    "runs_claimed_total": {"type": "counter", "unit": "1", "labels": ["role", "outcome"]},
    "run_queue_wait_seconds": {"type": "histogram", "unit": "s", "labels": ["role"]},
    "run_execute_seconds": {"type": "histogram", "unit": "s", "labels": ["engine", "outcome"]},
    "edge_jobs_claimed_total": {"type": "counter", "unit": "1", "labels": ["outcome"]},
    "spool_replay_total": {"type": "counter", "unit": "1", "labels": ["outcome"]},
    "connector_calls_total": {"type": "counter", "unit": "1", "labels": ["kind", "outcome"]},
    "lease_renew_total": {"type": "counter", "unit": "1", "labels": ["outcome"]},
    "artifact_stage_total": {"type": "counter", "unit": "1", "labels": ["stage", "outcome"]},
    "observe_errors_total": {"type": "counter", "unit": "1", "labels": ["stage"]},
}

_current_trace: ContextVar[ExecutionTrace | None] = ContextVar("execution_trace", default=None)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class ExecutionTrace:
    attrs: dict[str, str] = field(default_factory=dict)


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = {}

    def reset(self) -> None:
        self._counters.clear()
        self._histograms.clear()

    def _label_tuple(self, labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
        sanitized = _sanitize_labels(labels)
        return tuple(sorted(sanitized.items()))

    def increment(self, name: str, *, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
        key = (name, self._label_tuple(labels))
        self._counters[key] = self._counters.get(key, 0.0) + value

    def observe(self, name: str, seconds: float, *, labels: dict[str, str] | None = None) -> None:
        key = (name, self._label_tuple(labels))
        bucket = self._histograms.setdefault(key, [])
        bucket.append(max(0.0, float(seconds)))

    def snapshot(self) -> dict[str, Any]:
        counters: list[dict[str, Any]] = []
        for (name, label_tuple), value in sorted(self._counters.items()):
            labels = dict(label_tuple)
            definition = METRIC_DEFINITIONS.get(name, {})
            counters.append(
                {
                    "name": name,
                    "type": definition.get("type", "counter"),
                    "unit": definition.get("unit", "1"),
                    "labels": labels,
                    "value": value,
                }
            )
        histograms: list[dict[str, Any]] = []
        for (name, label_tuple), samples in sorted(self._histograms.items()):
            labels = dict(label_tuple)
            definition = METRIC_DEFINITIONS.get(name, {})
            histograms.append(
                {
                    "name": name,
                    "type": definition.get("type", "histogram"),
                    "unit": definition.get("unit", "s"),
                    "labels": labels,
                    "count": len(samples),
                    "sum": sum(samples),
                }
            )
        return {
            "definitions": METRIC_DEFINITIONS,
            "counters": counters,
            "histograms": histograms,
        }


_registry = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    return _registry


def get_current_trace() -> ExecutionTrace | None:
    return _current_trace.get()


def normalize_request_trace_id(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped or len(stripped) > TRACE_ID_MAX_LEN:
        return None
    if not _TRACE_ID_PATTERN.match(stripped):
        return None
    return stripped


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    if normalized == "secret_ref_id" or normalized.endswith("_secret_ref_id"):
        return False
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _looks_like_uuid(value: str) -> bool:
    return bool(_UUID_PATTERN.match(value))


def _sanitize_attr_value(key: str, value: Any) -> str | None:
    if key not in ALLOWED_TRACE_ATTRS:
        return None
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return None
    if isinstance(value, (dict, list)):
        return None
    text = str(value).strip()
    if not text:
        return None
    if _is_sensitive_key(key):
        return None
    if key == "request_trace_id":
        return normalize_request_trace_id(text)
    if len(text) > 256:
        text = text[:256]
    return text


def _sanitize_labels(labels: dict[str, str] | None) -> dict[str, str]:
    if not labels:
        return {}
    sanitized: dict[str, str] = {}
    for raw_key, raw_value in labels.items():
        key = str(raw_key).strip()
        if key not in ALLOWED_LABEL_KEYS:
            continue
        value = str(raw_value).strip()
        if not value or _is_sensitive_key(key) or _looks_like_uuid(value):
            continue
        sanitized[key] = value[:64]
    return sanitized


def bind_from_snapshot(
    snapshot: dict[str, Any] | None,
    *,
    run_id: str | None = None,
    attempt_id: str | None = None,
    generation: int | None = None,
    delivery_generation: int | None = None,
    step_id: str | None = None,
    edge_node_id: str | None = None,
) -> ExecutionTrace | None:
    try:
        snap = snapshot or {}
        attrs: dict[str, str] = {}
        candidates = {
            "run_id": run_id,
            "attempt_id": attempt_id,
            "session_id": snap.get("run_session_id"),
            "skill_release_id": snap.get("skill_release_id"),
            "step_id": step_id,
            "generation": generation,
            "delivery_generation": delivery_generation,
            "edge_node_id": edge_node_id or (snap.get("placement") or {}).get("edge_node_id"),
            "request_trace_id": snap.get("request_trace_id"),
        }
        for key, value in candidates.items():
            sanitized = _sanitize_attr_value(key, value)
            if sanitized is not None:
                attrs[key] = sanitized
        trace = ExecutionTrace(attrs=attrs)
        _current_trace.set(trace)
        return trace
    except Exception:
        logger.debug("bind_from_snapshot failed", exc_info=True)
        record_metric("observe_errors_total", labels={"stage": "bind"}, increment=1)
        return None


def observe_stage(stage: str, *, outcome: str = "ok", **attrs: Any) -> None:
    try:
        trace = _current_trace.get()
        if trace is None:
            trace = ExecutionTrace()
            _current_trace.set(trace)
        stage_value = _sanitize_attr_value("stage", stage)
        outcome_value = _sanitize_attr_value("outcome", outcome)
        if stage_value:
            trace.attrs["stage"] = stage_value
        if outcome_value:
            trace.attrs["outcome"] = outcome_value
        for key, value in attrs.items():
            sanitized = _sanitize_attr_value(key, value)
            if sanitized is not None:
                trace.attrs[key] = sanitized
    except Exception:
        logger.debug("observe_stage failed stage=%s", stage, exc_info=True)
        record_metric("observe_errors_total", labels={"stage": "observe_stage"}, increment=1)


def record_metric(
    name: str,
    *,
    labels: dict[str, str] | None = None,
    increment: float = 1.0,
    observe_seconds: float | None = None,
) -> None:
    try:
        if name not in METRIC_DEFINITIONS:
            return
        if observe_seconds is not None:
            _registry.observe(name, observe_seconds, labels=labels)
        else:
            _registry.increment(name, labels=labels, value=increment)
    except Exception:
        logger.debug("record_metric failed name=%s", name, exc_info=True)
        try:
            _registry.increment("observe_errors_total", labels={"stage": "record_metric"}, value=1.0)
        except Exception:
            logger.debug("observe_errors_total increment failed", exc_info=True)


def fail_open(func: F) -> F:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.debug("fail_open wrapper caught error in %s", func.__name__, exc_info=True)
            record_metric("observe_errors_total", labels={"stage": func.__name__}, increment=1)
            return None

    wrapper.__name__ = getattr(func, "__name__", "wrapped")
    wrapper.__doc__ = func.__doc__
    return wrapper  # type: ignore[return-value]


class observe_timer:
    def __init__(self, metric_name: str, *, labels: dict[str, str] | None = None) -> None:
        self._metric_name = metric_name
        self._labels = labels
        self._started: float | None = None

    def __enter__(self) -> observe_timer:
        self._started = time.monotonic()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if self._started is None:
            return False
        elapsed = time.monotonic() - self._started
        outcome = "error" if exc is not None else "ok"
        labels = dict(self._labels or {})
        if "outcome" not in labels:
            labels["outcome"] = outcome
        record_metric(self._metric_name, labels=labels, observe_seconds=elapsed)
        return False
