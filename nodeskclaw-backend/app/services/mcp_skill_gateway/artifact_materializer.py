from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.hermes_skill.hermes_task import HermesTask

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_FORBIDDEN_CONTENT = re.compile(
    r"(ndsk_mcp_[^\s]+|Bearer\s+\S+|Authorization:\s*\S+|NODESKCLAW_MCP_TOKEN)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ArtifactContent:
    filename: str
    content: bytes
    mime_type: str
    format: str
    suggested_workspace_dir: str
    suggested_workspace_path: str


def _sanitize_filename_part(value: str) -> str:
    cleaned = _INVALID_FILENAME_CHARS.sub("_", value.strip())
    return cleaned[:120] or "report"


def _format_date(dt: datetime | None = None) -> str:
    when = dt or datetime.now(timezone.utc)
    return when.strftime("%Y%m%d_%H%M")


_COMPANY_PROMPT_PATTERNS = [
    re.compile(r"为(.+?)做客户画像"),
    re.compile(r"分析(.+?)的客户画像"),
    re.compile(r"(.+?)客户画像"),
    re.compile(r"公司[：:]\s*(.+)"),
    re.compile(r"企业[：:]\s*(.+)"),
    re.compile(r"客户[：:]\s*(.+)"),
]

_COMPANY_ARG_KEYS = (
    "company",
    "company_name",
    "customer",
    "customer_name",
    "enterprise",
    "enterprise_name",
    "name",
)


def extract_company_from_task(task: HermesTask) -> str:
    args = task.arguments or {}

    for key in _COMPANY_ARG_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    context = args.get("context")
    if isinstance(context, dict):
        for key in _COMPANY_ARG_KEYS:
            value = context.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    prompt = str(args.get("prompt") or task.request_summary or "")
    for pattern in _COMPANY_PROMPT_PATTERNS:
        match = pattern.search(prompt)
        if match:
            value = match.group(1).strip(" ，。,.：:；;")
            if value:
                return value

    return "unknown"


def render_filename(template: str, task: HermesTask, *, completed_at: datetime | None = None) -> str:
    args = task.arguments or {}
    replacements = {
        "topic": _sanitize_filename_part(str(args.get("topic") or args.get("subject") or task.request_summary or "report")),
        "company": _sanitize_filename_part(extract_company_from_task(task)),
        "date": _format_date(completed_at),
    }
    filename = template
    for key, value in replacements.items():
        filename = filename.replace(f"{{{key}}}", value)
    filename = _INVALID_FILENAME_CHARS.sub("_", filename)
    return filename[:255]


def build_suggested_workspace_path(suggested_dir: str, filename: str) -> str:
    dir_part = suggested_dir.strip("/").strip()
    return f"workspace/{dir_part}/{filename}" if dir_part else f"workspace/{filename}"


def _strip_forbidden(text: str) -> str:
    return _FORBIDDEN_CONTENT.sub("[REDACTED]", text)


class ArtifactMaterializer:
    @staticmethod
    def materialize(
        task: HermesTask,
        full_result_text: str,
        output_policy: dict[str, Any],
        *,
        artifact_id: str | None = None,
        completed_at: datetime | None = None,
    ) -> ArtifactContent:
        fmt = str(output_policy.get("format") or "markdown").lower()
        template = str(output_policy.get("filename_template") or "{topic}_报告_{date}.md")
        suggested_dir = str(output_policy.get("suggested_workspace_dir") or "drafts/misc")
        filename = render_filename(template, task, completed_at=completed_at)
        suggested_path = build_suggested_workspace_path(suggested_dir, filename)
        artifact_id = artifact_id or str(uuid.uuid4())
        body = _strip_forbidden(full_result_text or "")

        kb_status = "none"
        kb = output_policy.get("kb_ingest") or {}
        if kb.get("enabled"):
            kb_status = str(kb.get("mode") or "pending_review")

        if fmt == "json":
            content_text = json.dumps(
                {
                    "task_id": task.id,
                    "tool_name": task.tool_name,
                    "artifact_id": artifact_id,
                    "result": body,
                },
                ensure_ascii=False,
                indent=2,
            )
            if not filename.endswith(".json"):
                filename = f"{path_stem(filename)}.json"
            return ArtifactContent(
                filename=filename,
                content=content_text.encode("utf-8"),
                mime_type="application/json",
                format="json",
                suggested_workspace_dir=suggested_dir,
                suggested_workspace_path=build_suggested_workspace_path(suggested_dir, filename),
            )

        if fmt == "txt":
            content_text = body
            if not filename.endswith(".txt"):
                filename = f"{path_stem(filename)}.txt"
            return ArtifactContent(
                filename=filename,
                content=content_text.encode("utf-8"),
                mime_type="text/plain",
                format="txt",
                suggested_workspace_dir=suggested_dir,
                suggested_workspace_path=build_suggested_workspace_path(suggested_dir, filename),
            )

        created_label = (completed_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M")
        frontmatter = (
            "---\n"
            "source: nodeskclaw-mcp-skill-gateway\n"
            f"task_id: {task.id}\n"
            f"tool_name: {task.tool_name or ''}\n"
            f"artifact_id: {artifact_id}\n"
            f"created_at: {created_label}\n"
            f"kb_status: {kb_status}\n"
            "---\n\n"
        )
        title = task.request_summary or task.tool_name or "Report"
        content_text = f"{frontmatter}# {title}\n\n{body}"
        if not filename.endswith(".md"):
            filename = f"{path_stem(filename)}.md"
        return ArtifactContent(
            filename=filename,
            content=content_text.encode("utf-8"),
            mime_type="text/markdown",
            format="markdown",
            suggested_workspace_dir=suggested_dir,
            suggested_workspace_path=build_suggested_workspace_path(suggested_dir, filename),
        )


def path_stem(name: str) -> str:
    if "." in name:
        return name.rsplit(".", 1)[0]
    return name
