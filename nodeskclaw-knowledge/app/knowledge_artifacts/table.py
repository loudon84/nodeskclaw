"""Table artifact provider — canonical TableArtifact from parsed table chunks."""

# @lat: [[architecture/knowledge#Knowledge Intelligence V23]]

from __future__ import annotations

import json
import re
from typing import Any

from app.knowledge_artifacts.base import (
    ArtifactBuildContext,
    ArtifactBuildResult,
    ArtifactCapability,
    ArtifactDelta,
    ArtifactEvidenceCandidate,
    ArtifactValidationResult,
    SourceRef,
)
from app.services import artifact_store

_TABLE_CHUNK_MARKERS = frozenset({"table", "html-table", "html_table", "structured_table"})


def _chunk_metadata(chunk: dict[str, Any]) -> dict[str, Any]:
    meta = chunk.get("document_metadata") or chunk.get("metadata") or {}
    return meta if isinstance(meta, dict) else {}


def _is_table_chunk(chunk: dict[str, Any]) -> bool:
    meta = _chunk_metadata(chunk)
    chunk_type = str(meta.get("type") or meta.get("chunk_type") or chunk.get("type") or "").lower()
    if any(marker in chunk_type for marker in _TABLE_CHUNK_MARKERS):
        return True
    content_type = str(meta.get("content_type") or "").lower()
    if "table" in content_type:
        return True
    if meta.get("table_id") or meta.get("columns") or meta.get("table"):
        return True
    return False


def _normalize_column(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        name = raw.get("name") or raw.get("id") or raw.get("key") or ""
        col_type = raw.get("type") or raw.get("data_type") or "string"
        return {"name": str(name), "type": str(col_type)}
    return {"name": str(raw), "type": "string"}


def _normalize_source_ref(
    raw: dict[str, Any],
    *,
    context: ArtifactBuildContext,
    chunk: dict[str, Any],
) -> dict[str, Any] | None:
    meta = _chunk_metadata(chunk)
    source_file_id = raw.get("source_file_id") or meta.get("nk_source_file_id") or context.source_file_id
    file_version_id = raw.get("file_version_id") or meta.get("nk_file_version_id") or context.file_version_id
    if not source_file_id or not file_version_id:
        return None
    return {
        "source_file_id": str(source_file_id),
        "file_version_id": str(file_version_id),
        "page_start": raw.get("page_start") or raw.get("page") or meta.get("page"),
        "page_end": raw.get("page_end"),
        "chunk_id": str(raw.get("chunk_id") or chunk.get("id") or chunk.get("chunk_id") or ""),
    }


def _default_source_ref(context: ArtifactBuildContext, chunk: dict[str, Any]) -> dict[str, Any] | None:
    meta = _chunk_metadata(chunk)
    source_file_id = meta.get("nk_source_file_id") or context.source_file_id
    file_version_id = meta.get("nk_file_version_id") or context.file_version_id
    if not source_file_id or not file_version_id:
        return None
    chunk_id = str(chunk.get("id") or chunk.get("chunk_id") or "")
    return {
        "source_file_id": str(source_file_id),
        "file_version_id": str(file_version_id),
        "page_start": meta.get("page_start") or meta.get("page"),
        "page_end": meta.get("page_end"),
        "chunk_id": chunk_id or None,
    }


def _parse_table_payload(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    columns_raw = raw.get("columns") or raw.get("headers") or []
    rows_raw = raw.get("rows") or raw.get("data") or []
    if not columns_raw and not rows_raw:
        return None
    columns = [_normalize_column(col) for col in columns_raw] if isinstance(columns_raw, list) else []
    return {
        "table_id": str(raw.get("table_id") or raw.get("id") or ""),
        "columns": columns,
        "rows_raw": rows_raw if isinstance(rows_raw, list) else [],
    }


def _table_from_chunk(chunk: dict[str, Any], context: ArtifactBuildContext) -> dict[str, Any] | None:
    meta = _chunk_metadata(chunk)
    payload = _parse_table_payload(meta.get("table"))
    if payload is None:
        payload = _parse_table_payload(chunk.get("table"))
    if payload is None:
        content = chunk.get("content")
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                payload = _parse_table_payload(parsed)
    if payload is None:
        return None
    default_ref = _default_source_ref(context, chunk)
    rows: list[dict[str, Any]] = []
    for idx, raw_row in enumerate(payload["rows_raw"]):
        if not isinstance(raw_row, dict):
            continue
        values = raw_row.get("values")
        if values is None:
            values = raw_row.get("cells") or {
                key: value
                for key, value in raw_row.items()
                if key not in {"row_id", "id", "source_refs", "sources", "lineage"}
            }
        source_refs: list[dict[str, Any]] = []
        for key in ("source_refs", "sources", "lineage"):
            refs = raw_row.get(key)
            if isinstance(refs, list):
                for ref in refs:
                    if not isinstance(ref, dict):
                        continue
                    normalized = _normalize_source_ref(ref, context=context, chunk=chunk)
                    if normalized:
                        source_refs.append(normalized)
        if not source_refs and default_ref:
            source_refs.append(default_ref)
        rows.append(
            {
                "row_id": str(raw_row.get("row_id") or raw_row.get("id") or idx),
                "values": values if isinstance(values, dict) else {"value": values},
                "source_refs": source_refs,
            }
        )
    table_id = payload["table_id"] or str(chunk.get("id") or chunk.get("chunk_id") or "")
    return {
        "table_id": table_id,
        "columns": payload["columns"],
        "rows": rows,
    }


async def _load_canonical_tables(context: ArtifactBuildContext) -> list[dict[str, Any]]:
    document_id = context.ragflow_document_id
    if not document_id:
        return []
    tables: list[dict[str, Any]] = []
    async for chunk in context.adapter.iter_document_chunks(
        context.dataset_id,
        document_id,
        page_size=100,
    ):
        if not isinstance(chunk, dict) or not _is_table_chunk(chunk):
            continue
        table = _table_from_chunk(chunk, context)
        if table and table.get("rows"):
            tables.append(table)
    return tables


def _flatten_tables(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in tables:
        table_id = table.get("table_id") or ""
        for row in table.get("rows") or []:
            if not isinstance(row, dict):
                continue
            rows.append(
                {
                    "table_id": table_id,
                    "row_id": row.get("row_id"),
                    "values": row.get("values") or {},
                    "source_refs": row.get("source_refs") or [],
                }
            )
    return rows


def _row_matches_query(row: dict[str, Any], query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    values = row.get("values") or {}
    if isinstance(values, dict):
        for value in values.values():
            if needle in str(value).lower():
                return True
    if re.search(r"\d", needle):
        blob = json.dumps(row, ensure_ascii=False)
        if needle in blob.lower():
            return True
    return False


def filter_table_candidates_by_acl(
    candidates: list[ArtifactEvidenceCandidate],
    allowed_source_file_ids: set[str],
) -> list[ArtifactEvidenceCandidate]:
    if not allowed_source_file_ids:
        return []
    filtered: list[ArtifactEvidenceCandidate] = []
    for candidate in candidates:
        refs = [
            ref
            for ref in candidate.source_refs
            if ref.source_file_id in allowed_source_file_ids
        ]
        if not refs:
            continue
        filtered.append(
            ArtifactEvidenceCandidate(
                artifact_type=candidate.artifact_type,
                title=candidate.title,
                content=candidate.content,
                source_refs=refs,
                citable=bool(refs),
                provider_payload=dict(candidate.provider_payload),
            )
        )
    return filtered


class TableArtifactProvider:
    artifact_type = "table"

    def capabilities(self) -> ArtifactCapability:
        return ArtifactCapability(
            artifact_type=self.artifact_type,
            provider="ragflow_native",
            scope="file",
            build_supported=True,
            retrieval_supported=True,
            incremental_supported=True,
        )

    async def build(self, context: ArtifactBuildContext) -> ArtifactBuildResult:
        tables = await _load_canonical_tables(context)
        flat_rows = _flatten_tables(tables)
        if not flat_rows:
            return ArtifactBuildResult(
                status="failed",
                error_code="table_unavailable",
                error_message="no table rows available from document chunks",
            )
        payload = {"artifact_type": self.artifact_type, "tables": tables}
        relative_path = (
            f"{context.org_id}/{context.knowledge_base_id}/table/"
            f"{context.source_file_id or 'kb'}/{context.manifest_hash}.json"
        )
        artifact_uri = artifact_store.write_bytes(
            relative_path,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )
        citable_rows = sum(1 for row in flat_rows if row.get("source_refs"))
        return ArtifactBuildResult(
            status="succeeded",
            artifact_uri=artifact_uri,
            provider_payload={"row_count": len(flat_rows), "citable_rows": citable_rows, "table_count": len(tables)},
            validation_payload={"ready": True, "row_count": len(flat_rows), "citable_rows": citable_rows},
            coverage_payload={"row_count": len(flat_rows)},
        )

    async def validate(self, context: ArtifactBuildContext) -> ArtifactValidationResult:
        tables = await _load_canonical_tables(context)
        flat_rows = _flatten_tables(tables)
        citable_rows = sum(1 for row in flat_rows if row.get("source_refs"))
        ready = len(flat_rows) > 0
        return ArtifactValidationResult(
            ready=ready,
            validation_payload={
                "artifact_type": self.artifact_type,
                "row_count": len(flat_rows),
                "citable_rows": citable_rows,
                "table_count": len(tables),
            },
            coverage_payload={"citable_ratio": (citable_rows / len(flat_rows)) if flat_rows else 0.0},
        )

    async def retrieve(
        self,
        query: str,
        context: ArtifactBuildContext,
    ) -> list[ArtifactEvidenceCandidate]:
        tables = await _load_canonical_tables(context)
        flat_rows = _flatten_tables(tables)
        candidates: list[ArtifactEvidenceCandidate] = []
        for row in flat_rows:
            if not _row_matches_query(row, query):
                continue
            refs = await self.resolve_lineage(row)
            values = row.get("values") or {}
            title = str(row.get("row_id") or "table_row")
            if isinstance(values, dict) and values:
                title = ", ".join(f"{key}={value}" for key, value in list(values.items())[:3])
            content = json.dumps(values, ensure_ascii=False)
            candidates.append(
                ArtifactEvidenceCandidate(
                    artifact_type=self.artifact_type,
                    title=title,
                    content=content,
                    source_refs=refs,
                    citable=bool(refs),
                    provider_payload={
                        "evidence_type": "table_row",
                        "row_id": row.get("row_id"),
                        "table_id": row.get("table_id"),
                        "artifact_type": self.artifact_type,
                    },
                )
            )
        return candidates

    async def resolve_lineage(self, item: dict[str, Any]) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for raw in item.get("source_refs") or []:
            if not isinstance(raw, dict):
                continue
            source_file_id = raw.get("source_file_id")
            file_version_id = raw.get("file_version_id")
            if source_file_id and file_version_id:
                refs.append(
                    SourceRef(
                        source_file_id=str(source_file_id),
                        file_version_id=str(file_version_id),
                        page_start=raw.get("page_start"),
                        page_end=raw.get("page_end"),
                        chunk_id=str(raw["chunk_id"]) if raw.get("chunk_id") else None,
                    )
                )
        return refs

    async def diff(self, context: ArtifactBuildContext) -> ArtifactDelta:
        alteration = await context.adapter.get_artifact_alteration(context.dataset_id)
        return ArtifactDelta(
            added=[str(x) for x in (alteration.get("newly_uploaded") or [])],
            changed=[str(x) for x in (alteration.get("changed") or [])],
            removed=[str(x) for x in (alteration.get("removed") or [])],
        )
