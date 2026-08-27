"""Table artifact provider — structured row evidence from RAGFlow alteration payload."""

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


def _normalize_row(raw: dict[str, Any], *, row_index: int) -> dict[str, Any]:
    source_refs: list[dict[str, Any]] = []
    for key in ("source_refs", "sources", "lineage"):
        refs = raw.get(key)
        if isinstance(refs, list):
            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                source_file_id = ref.get("source_file_id")
                file_version_id = ref.get("file_version_id")
                if source_file_id and file_version_id:
                    source_refs.append(
                        {
                            "source_file_id": str(source_file_id),
                            "file_version_id": str(file_version_id),
                            "page_start": ref.get("page_start") or ref.get("page"),
                            "page_end": ref.get("page_end"),
                            "chunk_id": ref.get("chunk_id"),
                        }
                    )
    if not source_refs and raw.get("source_file_id") and raw.get("file_version_id"):
        source_refs.append(
            {
                "source_file_id": str(raw["source_file_id"]),
                "file_version_id": str(raw["file_version_id"]),
                "page_start": raw.get("page_start") or raw.get("page"),
                "page_end": raw.get("page_end"),
                "chunk_id": raw.get("chunk_id"),
            }
        )
    row_id = str(raw.get("id") or raw.get("row_id") or row_index)
    cells = raw.get("cells") or raw.get("values") or raw
    return {
        "id": row_id,
        "header": str(raw.get("header") or raw.get("title") or ""),
        "cells": cells if isinstance(cells, dict) else {"value": cells},
        "source_refs": source_refs,
        "citable": len(source_refs) > 0,
    }


def _rows_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = payload.get("rows") or (payload.get("data") or {}).get("rows") or payload.get("tables") or []
    if not isinstance(raw_rows, list):
        return []
    return [_normalize_row(row, row_index=idx) for idx, row in enumerate(raw_rows) if isinstance(row, dict)]


def _row_matches_query(row: dict[str, Any], query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    header = str(row.get("header") or "").lower()
    if needle in header:
        return True
    cells = row.get("cells") or {}
    if isinstance(cells, dict):
        for value in cells.values():
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
        params: dict[str, Any] = {}
        if context.ragflow_document_id:
            params["document_id"] = context.ragflow_document_id
        alteration = await context.adapter.get_artifact_alteration(context.dataset_id, **params)
        rows = _rows_from_payload(alteration if isinstance(alteration, dict) else {})
        if not rows:
            return ArtifactBuildResult(
                status="failed",
                error_code="table_unavailable",
                error_message="no table rows available from runtime",
            )
        payload = {"artifact_type": self.artifact_type, "rows": rows}
        relative_path = (
            f"{context.org_id}/{context.knowledge_base_id}/table/"
            f"{context.source_file_id or 'kb'}/{context.manifest_hash}.json"
        )
        artifact_uri = artifact_store.write_bytes(
            relative_path,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )
        citable_rows = sum(1 for row in rows if row.get("citable"))
        return ArtifactBuildResult(
            status="succeeded",
            artifact_uri=artifact_uri,
            provider_payload={"row_count": len(rows), "citable_rows": citable_rows},
            validation_payload={"ready": True, "row_count": len(rows), "citable_rows": citable_rows},
            coverage_payload={"row_count": len(rows)},
        )

    async def validate(self, context: ArtifactBuildContext) -> ArtifactValidationResult:
        params: dict[str, Any] = {}
        if context.ragflow_document_id:
            params["document_id"] = context.ragflow_document_id
        alteration = await context.adapter.get_artifact_alteration(context.dataset_id, **params)
        rows = _rows_from_payload(alteration if isinstance(alteration, dict) else {})
        citable_rows = sum(1 for row in rows if row.get("citable"))
        ready = len(rows) > 0
        return ArtifactValidationResult(
            ready=ready,
            validation_payload={
                "artifact_type": self.artifact_type,
                "row_count": len(rows),
                "citable_rows": citable_rows,
            },
            coverage_payload={"citable_ratio": (citable_rows / len(rows)) if rows else 0.0},
        )

    async def retrieve(
        self,
        query: str,
        context: ArtifactBuildContext,
    ) -> list[ArtifactEvidenceCandidate]:
        params: dict[str, Any] = {}
        if context.ragflow_document_id:
            params["document_id"] = context.ragflow_document_id
        alteration = await context.adapter.get_artifact_alteration(context.dataset_id, **params)
        rows = _rows_from_payload(alteration if isinstance(alteration, dict) else {})
        candidates: list[ArtifactEvidenceCandidate] = []
        for row in rows:
            if not _row_matches_query(row, query):
                continue
            refs = await self.resolve_lineage(row)
            title = str(row.get("header") or row.get("id") or "table_row")
            content = json.dumps(row.get("cells") or row, ensure_ascii=False)
            candidates.append(
                ArtifactEvidenceCandidate(
                    artifact_type=self.artifact_type,
                    title=title,
                    content=content,
                    source_refs=refs,
                    citable=bool(refs),
                    provider_payload={
                        "evidence_type": "table_row",
                        "row_id": row.get("id"),
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
