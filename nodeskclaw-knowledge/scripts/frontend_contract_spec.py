"""Canonical frontend contract v1.0.0 spec: endpoint matrix + JSON schemas."""

from __future__ import annotations

PROVIDER_RUNTIME_ID_KEYS = (
    "dataset_id",
    "document_id",
    "chunk_id",
    "ragflow_document_id",
    "ragflow_chunk_id",
    "ragflow_dataset_id",
)

STABILITY_VALUES = ("stable", "compatibility", "stable-compat", "optional")

NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_INTEGER = {"type": ["integer", "null"]}
NULLABLE_NUMBER = {"type": ["number", "null"]}
NULLABLE_OBJECT = {"type": ["object", "null"]}
NULLABLE_ARRAY = {"type": ["array", "null"]}


def _obj(properties: dict, required: list[str] | None = None, extra: bool = False) -> dict:
    schema: dict = {
        "type": "object",
        "properties": properties,
        "additionalProperties": extra,
    }
    if required:
        schema["required"] = required
    return schema


def _enum(values: list[str]) -> dict:
    return {"type": "string", "enum": values}


KB_STATUS = _enum(["provisioning", "active", "updating", "degraded", "error", "deleting"])
SOURCE_STATUS = _enum(["pending", "active", "updating", "error", "deleting"])
PARSE_STATUS = _enum(["pending", "parsing", "active", "failed", "superseded"])
INGESTION_STATUS = _enum(
    [
        "pending",
        "uploading",
        "upload_unknown",
        "ragflow_uploaded",
        "metadata_synced",
        "parse_dispatched",
        "parsing",
        "validating",
        "active",
        "failed",
        "cancelled",
    ]
)
BUILD_STATUS = _enum(["queued", "running", "completed", "partial", "failed", "cancelled"])
INDEX_BUILD = _enum(["not_built", "building", "ready", "stale", "failed", "unsupported"])
INDEX_RETRIEVAL = _enum(["unavailable", "ready", "degraded", "unsupported"])
APP_STATUS = _enum(["draft", "active", "disabled"])
RELEASE_STATUS = _enum(
    ["draft", "validating", "validated", "promoted", "superseded", "retired", "failed"]
)
CHANNEL = _enum(["preview", "stable"])
VISIBILITY = _enum(["private", "department", "organization"])
PROFILE_STATUS = _enum(["draft", "active", "archived"])
POLICY_STATUS = _enum(["draft", "active", "archived"])
SET_STATUS = _enum(["active", "disabled"])
RETRIEVAL_STATUS = _enum(["success", "empty", "degraded"])
SOURCE_KIND = _enum(["manual", "connector"])
ACL_EFFECT = _enum(["allow", "deny"])
SUBJECT_TYPE = _enum(["member", "role", "department", "organization"])


def _schema_doc(schema_id: str, title: str, body: dict) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:nodeskclaw:knowledge:frontend:v1:{schema_id}",
        "title": title,
        **body,
    }


SCHEMAS: dict[str, dict] = {
    "api-response": _schema_doc(
        "api-response",
        "ApiResponse",
        _obj(
            {
                "code": {"type": "integer"},
                "error_code": {"type": ["integer", "null"]},
                "message_key": {"type": ["string", "null"]},
                "message": {"type": "string"},
                "data": True,
                "details": {"type": "object"},
                "message_params": {"type": "object", "additionalProperties": {"type": "string"}},
            },
            ["code", "message", "data"],
            extra=False,
        ),
    ),
    "error-response": _schema_doc(
        "error-response",
        "ErrorResponse",
        _obj(
            {
                "code": {"type": "integer", "minimum": 40000},
                "error_code": {"type": "integer", "minimum": 40000},
                "message_key": {"type": "string"},
                "message": {"type": "string"},
                "data": {"type": "null"},
                "details": {"type": "object"},
                "message_params": {"type": "object", "additionalProperties": {"type": "string"}},
            },
            ["code", "error_code", "message_key", "message", "data"],
            extra=False,
        ),
    ),
    "page-data": _schema_doc(
        "page-data",
        "PageData",
        _obj(
            {
                "items": {"type": "array"},
                "total": {"type": "integer", "minimum": 0},
                "page": {"type": "integer", "minimum": 1},
                "page_size": {"type": "integer", "minimum": 1},
            },
            ["items", "total", "page", "page_size"],
        ),
    ),
    "health-ready": _schema_doc(
        "health-ready",
        "HealthReady",
        _obj(
            {
                "status": _enum(["ok", "not_ready"]),
                "checks": _obj(
                    {
                        "database": {"type": "boolean"},
                        "ragflow": {"type": "boolean"},
                        "backend": {"type": "boolean"},
                    },
                    ["database", "ragflow", "backend"],
                ),
            },
            ["status", "checks"],
        ),
    ),
    "knowledge-base": _schema_doc(
        "knowledge-base",
        "KnowledgeBase",
        _obj(
            {
                "id": {"type": "string"},
                "org_id": {"type": "string"},
                "name": {"type": "string"},
                "description": NULLABLE_STRING,
                "embedding_model": {"type": "string"},
                "chunk_method": {"type": "string"},
                "status": KB_STATUS,
                "owner_member_id": {"type": "string"},
                "acl_version": {"type": "integer"},
                "visibility": VISIBILITY,
                "tags": {"type": ["array", "null"], "items": {"type": "string"}},
                "active_build_profile_id": NULLABLE_STRING,
                "knowledge_model_id": NULLABLE_STRING,
                "build_version": {"type": "integer", "minimum": 0},
            },
            [
                "id",
                "org_id",
                "name",
                "embedding_model",
                "chunk_method",
                "status",
                "owner_member_id",
                "acl_version",
                "visibility",
                "build_version",
            ],
        ),
    ),
    "knowledge-base-create": _schema_doc(
        "knowledge-base-create",
        "KnowledgeBaseCreate",
        _obj(
            {
                "name": {"type": "string", "minLength": 1, "maxLength": 128},
                "description": NULLABLE_STRING,
                "embedding_model": {"type": "string"},
                "chunk_method": {"type": "string"},
                "parser_config": NULLABLE_OBJECT,
                "visibility": VISIBILITY,
                "tags": {"type": ["array", "null"], "items": {"type": "string"}},
            },
            ["name"],
        ),
    ),
    "knowledge-base-update": _schema_doc(
        "knowledge-base-update",
        "KnowledgeBaseUpdate",
        _obj(
            {
                "name": {"type": "string", "minLength": 1, "maxLength": 128},
                "description": NULLABLE_STRING,
                "tags": {"type": ["array", "null"], "items": {"type": "string"}},
                "visibility": VISIBILITY,
            }
        ),
    ),
    "knowledge-set": _schema_doc(
        "knowledge-set",
        "KnowledgeSet",
        _obj(
            {
                "id": {"type": "string"},
                "org_id": {"type": "string"},
                "name": {"type": "string"},
                "description": NULLABLE_STRING,
                "owner_member_id": {"type": "string"},
                "status": SET_STATUS,
                "acl_version": {"type": "integer"},
                "visibility": VISIBILITY,
                "retrieval_config": NULLABLE_OBJECT,
                "usage_count": {"type": "integer"},
                "last_used_at": True,
                "knowledge_bases": {
                    "type": ["array", "null"],
                    "items": _obj(
                        {
                            "knowledge_base_id": {"type": "string"},
                            "name": {"type": "string"},
                            "weight": {"type": "number"},
                        },
                        ["knowledge_base_id"],
                    ),
                },
            },
            [
                "id",
                "org_id",
                "name",
                "owner_member_id",
                "status",
                "acl_version",
                "visibility",
                "usage_count",
            ],
        ),
    ),
    "knowledge-set-create": _schema_doc(
        "knowledge-set-create",
        "KnowledgeSetCreate",
        _obj(
            {
                "name": {"type": "string", "minLength": 1, "maxLength": 128},
                "description": NULLABLE_STRING,
                "visibility": VISIBILITY,
                "retrieval_config": NULLABLE_OBJECT,
            },
            ["name"],
        ),
    ),
    "knowledge-set-update": _schema_doc(
        "knowledge-set-update",
        "KnowledgeSetUpdate",
        _obj(
            {
                "name": {"type": "string", "minLength": 1, "maxLength": 128},
                "description": NULLABLE_STRING,
                "status": SET_STATUS,
                "visibility": VISIBILITY,
                "retrieval_config": NULLABLE_OBJECT,
            }
        ),
    ),
    "knowledge-set-bind": _schema_doc(
        "knowledge-set-bind",
        "KnowledgeSetBind",
        _obj(
            {
                "knowledge_base_id": {"type": "string"},
                "weight": {"type": "number"},
                "sort_order": {"type": "integer"},
            },
            ["knowledge_base_id"],
        ),
    ),
    "source-file": _schema_doc(
        "source-file",
        "SourceFile",
        _obj(
            {
                "id": {"type": "string"},
                "org_id": {"type": "string"},
                "knowledge_base_id": {"type": "string"},
                "file_name": {"type": "string"},
                "mime_type": NULLABLE_STRING,
                "owner_member_id": {"type": "string"},
                "active_version_id": NULLABLE_STRING,
                "status": SOURCE_STATUS,
                "acl_version": {"type": "integer"},
                "last_error": NULLABLE_STRING,
                "metadata": {"type": "object"},
                "metadata_revision": {"type": "integer"},
                "archived_at": True,
                "parse_status": NULLABLE_STRING,
                "chunk_count": NULLABLE_INTEGER,
                "version_no": NULLABLE_INTEGER,
                "source_kind": SOURCE_KIND,
                "connector_id": NULLABLE_STRING,
                "external_object_id": NULLABLE_STRING,
                "source_uri": NULLABLE_STRING,
                "source_path": NULLABLE_STRING,
                "source_revision": NULLABLE_STRING,
                "source_etag": NULLABLE_STRING,
                "source_modified_at": True,
                "source_metadata": {"type": "object"},
                "last_synced_at": True,
                "sync_state": NULLABLE_STRING,
                "archive_reason": NULLABLE_STRING,
            },
            [
                "id",
                "org_id",
                "knowledge_base_id",
                "file_name",
                "owner_member_id",
                "status",
                "acl_version",
            ],
        ),
    ),
    "source-file-version": _schema_doc(
        "source-file-version",
        "SourceFileVersion",
        _obj(
            {
                "id": {"type": "string"},
                "source_file_id": {"type": "string"},
                "version_no": {"type": "integer"},
                "file_size": NULLABLE_INTEGER,
                "sha256": NULLABLE_STRING,
                "parse_status": PARSE_STATUS,
                "chunk_count": NULLABLE_INTEGER,
                "token_count": NULLABLE_INTEGER,
                "uploaded_by_member_id": NULLABLE_STRING,
                "activated_at": True,
                "superseded_at": True,
                "created_at": True,
            },
            ["id", "source_file_id", "version_no", "parse_status"],
        ),
    ),
    "ingestion-job": _schema_doc(
        "ingestion-job",
        "IngestionJob",
        _obj(
            {
                "id": {"type": "string"},
                "source_file_id": {"type": "string"},
                "file_version_id": {"type": "string"},
                "status": INGESTION_STATUS,
                "progress": {"type": "integer", "minimum": 0, "maximum": 100},
                "error_code": NULLABLE_STRING,
                "error_message": NULLABLE_STRING,
                "attempt_count": {"type": "integer"},
                "max_attempts": {"type": "integer"},
                "next_run_at": True,
                "finished_at": True,
                "created_by_member_id": NULLABLE_STRING,
            },
            [
                "id",
                "source_file_id",
                "file_version_id",
                "status",
                "progress",
                "attempt_count",
                "max_attempts",
            ],
        ),
    ),
    "upload-accepted": _schema_doc(
        "upload-accepted",
        "UploadAccepted",
        _obj(
            {
                "source_file": {"$ref": "urn:nodeskclaw:knowledge:frontend:v1:source-file"},
                "file_version_id": {"type": "string"},
                "job": {"$ref": "urn:nodeskclaw:knowledge:frontend:v1:ingestion-job"},
            },
            ["source_file", "file_version_id", "job"],
        ),
    ),
    "index-state-map": _schema_doc(
        "index-state-map",
        "IndexStateMap",
        {
            "type": "object",
            "additionalProperties": _obj(
                {
                    "build_status": INDEX_BUILD,
                    "retrieval_status": INDEX_RETRIEVAL,
                    "last_error": {"type": "string"},
                    "validation": {"type": "object"},
                    "coverage": {"type": "object"},
                    "last_validated_at": {"type": "string"},
                    "runtime_feature": True,
                },
                ["build_status", "retrieval_status"],
            ),
        },
    ),
    "build-job": _schema_doc(
        "build-job",
        "BuildJob",
        _obj(
            {
                "id": {"type": "string"},
                "org_id": {"type": "string"},
                "knowledge_base_id": NULLABLE_STRING,
                "build_profile_id": NULLABLE_STRING,
                "index_type": NULLABLE_STRING,
                "trigger_reason": NULLABLE_STRING,
                "status": BUILD_STATUS,
                "progress": {"type": "integer", "minimum": 0, "maximum": 100},
                "error_code": NULLABLE_STRING,
                "error_message": NULLABLE_STRING,
                "attempt_count": {"type": "integer"},
                "finished_at": True,
                "created_at": True,
            },
            ["id", "org_id", "status", "progress", "attempt_count"],
        ),
    ),
    "build-job-list": _schema_doc(
        "build-job-list",
        "BuildJobList",
        _obj({"jobs": {"type": "array", "items": {"$ref": "urn:nodeskclaw:knowledge:frontend:v1:build-job"}}}, ["jobs"]),
    ),
    "build-profile": _schema_doc(
        "build-profile",
        "BuildProfile",
        _obj(
            {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "description": NULLABLE_STRING,
                "system_key": NULLABLE_STRING,
                "is_system": {"type": "boolean"},
                "index_types": {"type": "array", "items": {"type": "string"}},
                "artifact_types": {"type": "array", "items": {"type": "string"}},
                "trigger_policy": {"type": "object"},
                "artifact_trigger_policy": {"type": "object"},
                "version": {"type": "integer"},
            },
            ["id", "name"],
        ),
    ),
    "build-profile-view": _schema_doc(
        "build-profile-view",
        "BuildProfileView",
        _obj(
            {
                "active_build_profile_id": NULLABLE_STRING,
                "resolved_profile": {"$ref": "urn:nodeskclaw:knowledge:frontend:v1:build-profile"},
            },
            ["resolved_profile"],
        ),
    ),
    "build-profile-update": _schema_doc(
        "build-profile-update",
        "BuildProfileUpdate",
        _obj({"build_profile_id": {"type": "string", "minLength": 1}}, ["build_profile_id"]),
    ),
    "trigger-builds": _schema_doc(
        "trigger-builds",
        "TriggerBuildsRequest",
        _obj(
            {
                "index_types": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "force": {"type": "boolean"},
            },
            ["index_types"],
        ),
    ),
    "acl": _schema_doc(
        "acl",
        "Acl",
        _obj(
            {
                "id": {"type": "string"},
                "subject_type": SUBJECT_TYPE,
                "subject_id": {"type": "string"},
                "permission": {"type": "string"},
                "effect": ACL_EFFECT,
                "created_by_member_id": {"type": "string"},
            },
            ["id", "subject_type", "subject_id", "permission", "effect", "created_by_member_id"],
        ),
    ),
    "acl-create": _schema_doc(
        "acl-create",
        "AclCreate",
        _obj(
            {
                "subject_type": SUBJECT_TYPE,
                "subject_id": {"type": "string", "minLength": 1},
                "permission": {"type": "string"},
                "effect": ACL_EFFECT,
                "role": {"type": "string"},
            },
            ["subject_type", "subject_id"],
        ),
    ),
    "metadata-schema": _schema_doc(
        "metadata-schema",
        "MetadataSchema",
        _obj({"fields": {"type": "array", "items": {"type": "object"}}}, ["fields"]),
    ),
    "retrieval-profile": _schema_doc(
        "retrieval-profile",
        "RetrievalProfile",
        _obj(
            {
                "id": {"type": "string"},
                "knowledge_set_id": {"type": "string"},
                "version": {"type": "integer"},
                "config": {"type": "object"},
                "status": PROFILE_STATUS,
                "created_by_member_id": {"type": "string"},
                "activated_at": True,
                "created_at": True,
                "updated_at": True,
            },
            ["id", "knowledge_set_id", "version", "config", "status", "created_by_member_id"],
        ),
    ),
    "retrieval-profile-create": _schema_doc(
        "retrieval-profile-create",
        "RetrievalProfileCreate",
        _obj({"config": NULLABLE_OBJECT}),
    ),
    "retrieval-profile-update": _schema_doc(
        "retrieval-profile-update",
        "RetrievalProfileUpdate",
        _obj({"config": {"type": "object"}}, ["config"]),
    ),
    "retrieval-profile-rollback": _schema_doc(
        "retrieval-profile-rollback",
        "RetrievalProfileRollback",
        _obj({"publish": {"type": "boolean"}}),
    ),
    "application": _schema_doc(
        "application",
        "KnowledgeApplication",
        _obj(
            {
                "id": {"type": "string"},
                "org_id": {"type": "string"},
                "name": {"type": "string"},
                "description": NULLABLE_STRING,
                "owner_member_id": {"type": "string"},
                "status": APP_STATUS,
                "answer_model": NULLABLE_STRING,
                "active_profile_id": NULLABLE_STRING,
                "acl_version": {"type": "integer"},
                "visibility": {"type": "string"},
                "knowledge_set_ids": {"type": "array", "items": {"type": "string"}},
                "validation_job_id": NULLABLE_STRING,
            },
            [
                "id",
                "org_id",
                "name",
                "owner_member_id",
                "status",
                "acl_version",
                "visibility",
                "knowledge_set_ids",
            ],
        ),
    ),
    "application-create": _schema_doc(
        "application-create",
        "KnowledgeApplicationCreate",
        _obj(
            {
                "name": {"type": "string", "minLength": 1, "maxLength": 128},
                "description": NULLABLE_STRING,
                "answer_model": NULLABLE_STRING,
                "knowledge_set_ids": {"type": "array", "items": {"type": "string"}},
            },
            ["name"],
        ),
    ),
    "application-update": _schema_doc(
        "application-update",
        "KnowledgeApplicationUpdate",
        _obj(
            {
                "name": {"type": "string", "minLength": 1, "maxLength": 128},
                "description": NULLABLE_STRING,
                "answer_model": NULLABLE_STRING,
            }
        ),
    ),
    "application-bind-set": _schema_doc(
        "application-bind-set",
        "KnowledgeApplicationBindSet",
        _obj(
            {"knowledge_set_id": {"type": "string"}, "sort_order": {"type": "integer"}},
            ["knowledge_set_id"],
        ),
    ),
    "application-publish": _schema_doc(
        "application-publish",
        "KnowledgeApplicationPublish",
        _obj({"promote_on_validated": {"type": "boolean"}}),
    ),
    "application-readiness": _schema_doc(
        "application-readiness",
        "ApplicationReadiness",
        _obj(
            {
                "ready": {"type": "boolean"},
                "blocking": {"type": "array"},
                "warnings": {"type": "array"},
            },
            extra=True,
        ),
    ),
    "release": _schema_doc(
        "release",
        "KnowledgeRelease",
        _obj(
            {
                "id": {"type": "string"},
                "application_id": {"type": "string"},
                "version": {"type": "integer"},
                "status": RELEASE_STATUS,
                "release_manifest": {"type": "object"},
                "manifest_hash": NULLABLE_STRING,
                "quality_snapshot_id": NULLABLE_STRING,
                "validation_job_id": NULLABLE_STRING,
                "created_by_member_id": {"type": "string"},
                "promoted_at": True,
                "retired_at": True,
                "validation_error": NULLABLE_STRING,
                "created_at": True,
            },
            ["id", "application_id", "version", "status", "release_manifest", "created_by_member_id"],
        ),
    ),
    "release-create": _schema_doc(
        "release-create",
        "KnowledgeReleaseCreate",
        _obj({"retrieval_policy_revision_id": NULLABLE_STRING}),
    ),
    "channel": _schema_doc(
        "channel",
        "ReleaseChannelState",
        _obj(
            {
                "id": {"type": "string"},
                "application_id": {"type": "string"},
                "channel": CHANNEL,
                "active_release_id": NULLABLE_STRING,
                "traffic_policy": NULLABLE_OBJECT,
                "updated_by_member_id": NULLABLE_STRING,
                "updated_at": True,
            },
            ["id", "application_id", "channel"],
        ),
    ),
    "release-promote": _schema_doc(
        "release-promote",
        "ReleasePromote",
        _obj({"release_id": {"type": "string"}}, ["release_id"]),
    ),
    "retrieval-policy-revision": _schema_doc(
        "retrieval-policy-revision",
        "RetrievalPolicyRevision",
        _obj(
            {
                "id": {"type": "string"},
                "application_id": {"type": "string"},
                "revision_number": {"type": "integer"},
                "status": POLICY_STATUS,
                "query_intelligence_policy": NULLABLE_OBJECT,
                "provider_policy": NULLABLE_OBJECT,
                "provider_weights": NULLABLE_OBJECT,
                "candidate_budget": NULLABLE_OBJECT,
                "fanout_budget": NULLABLE_OBJECT,
                "latency_budget": NULLABLE_OBJECT,
                "fallback_policy": NULLABLE_OBJECT,
                "artifact_policy": NULLABLE_OBJECT,
                "fusion_policy": NULLABLE_OBJECT,
                "created_by_member_id": {"type": "string"},
                "published_at": True,
                "notes": NULLABLE_STRING,
                "created_at": True,
            },
            ["id", "application_id", "revision_number", "status", "created_by_member_id"],
        ),
    ),
    "retrieval-policy-revision-create": _schema_doc(
        "retrieval-policy-revision-create",
        "RetrievalPolicyRevisionCreate",
        _obj(
            {
                "query_intelligence_policy": NULLABLE_OBJECT,
                "provider_policy": NULLABLE_OBJECT,
                "provider_weights": NULLABLE_OBJECT,
                "candidate_budget": NULLABLE_OBJECT,
                "fanout_budget": NULLABLE_OBJECT,
                "latency_budget": NULLABLE_OBJECT,
                "fallback_policy": NULLABLE_OBJECT,
                "artifact_policy": NULLABLE_OBJECT,
                "fusion_policy": NULLABLE_OBJECT,
                "notes": NULLABLE_STRING,
            }
        ),
    ),
    "evidence-item": _schema_doc(
        "evidence-item",
        "PublicEvidenceItem",
        _obj(
            {
                "evidence_id": {"type": "string"},
                "knowledge_base_id": NULLABLE_STRING,
                "source_file_id": NULLABLE_STRING,
                "file_version_id": NULLABLE_STRING,
                "file_name": NULLABLE_STRING,
                "content": {"type": "string"},
                "score": NULLABLE_NUMBER,
                "similarity": NULLABLE_NUMBER,
                "weighted_score": NULLABLE_NUMBER,
                "page": NULLABLE_INTEGER,
                "highlight": NULLABLE_STRING,
                "source_freshness": NULLABLE_STRING,
                "last_synced_at": True,
            },
            ["evidence_id"],
        ),
    ),
    "retrieval-response": _schema_doc(
        "retrieval-response",
        "ApplicationRetrievalData",
        _obj(
            {
                "application_id": {"type": "string"},
                "release_id": {"type": "string"},
                "channel": CHANNEL,
                "manifest_hash": {"type": "string"},
                "status": RETRIEVAL_STATUS,
                "answer_model": NULLABLE_STRING,
                "knowledge_set_ids": {"type": "array", "items": {"type": "string"}},
                "chunks": {
                    "type": "array",
                    "items": {"$ref": "urn:nodeskclaw:knowledge:frontend:v1:evidence-item"},
                },
            },
            ["application_id", "release_id", "channel", "manifest_hash"],
        ),
    ),
    "application-retrieval-request": _schema_doc(
        "application-retrieval-request",
        "ApplicationRetrievalRequest",
        _obj(
            {
                "query": {"type": "string", "minLength": 1},
                "top_k": NULLABLE_INTEGER,
                "similarity_threshold": NULLABLE_NUMBER,
                "filters": {"type": ["object", "null"]},
                "profile_id": NULLABLE_STRING,
            },
            ["query"],
        ),
    ),
    "playground-request": _schema_doc(
        "playground-request",
        "PlaygroundRequest",
        _obj(
            {
                "query": {"type": "string", "minLength": 1},
                "application_id": NULLABLE_STRING,
                "knowledge_set_id": NULLABLE_STRING,
                "profile_id": NULLABLE_STRING,
                "filters": {"type": ["object", "null"]},
                "include_trace": {"type": "boolean"},
            },
            ["query"],
        ),
    ),
    "playground-response": _schema_doc(
        "playground-response",
        "PlaygroundResponse",
        {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "chunks": {
                    "type": "array",
                    "items": {"$ref": "urn:nodeskclaw:knowledge:frontend:v1:evidence-item"},
                }
            },
        },
    ),
    "evidence": _schema_doc(
        "evidence",
        "EvidenceResolve",
        _obj(
            {
                "evidence_id": {"type": "string"},
                "citation_id": {"type": "string"},
                "message_id": NULLABLE_STRING,
                "org_id": {"type": "string"},
                "issued_member_id": {"type": "string"},
                "evidence_type": {"type": "string"},
                "content": NULLABLE_STRING,
                "source_refs": NULLABLE_ARRAY,
                "origin": {"type": "string"},
                "knowledge_base_id": {"type": "string"},
                "source_file_id": {"type": "string"},
                "file_version_id": {"type": "string"},
                "page": NULLABLE_INTEGER,
                "positions": NULLABLE_ARRAY,
                "score": NULLABLE_NUMBER,
                "quote": NULLABLE_STRING,
                "accessible": {"type": "boolean"},
                "reason": {"type": "string"},
                "source_kind": NULLABLE_STRING,
                "connector_type": NULLABLE_STRING,
                "connector_name": NULLABLE_STRING,
                "source_path": NULLABLE_STRING,
                "source_revision": NULLABLE_STRING,
                "source_modified_at": NULLABLE_STRING,
                "last_synced_at": NULLABLE_STRING,
                "sync_state": NULLABLE_STRING,
                "source_freshness": NULLABLE_STRING,
            },
            [
                "evidence_id",
                "knowledge_base_id",
                "source_file_id",
                "file_version_id",
                "accessible",
                "reason",
            ],
        ),
    ),
    "quality-snapshot": _schema_doc(
        "quality-snapshot",
        "QualitySnapshot",
        _obj(
            {
                "score_status": {"type": "string"},
                "subscores": {"type": "object"},
                "data_coverage": {"type": "object"},
                "issues": {"type": "array", "items": {"type": "string"}},
                "calculated_at": {"type": "string"},
                "application_id": {"type": "string"},
            },
            ["score_status"],
            extra=True,
        ),
    ),
    "quality-history": _schema_doc(
        "quality-history",
        "QualityHistory",
        _obj(
            {
                "history": {
                    "type": "array",
                    "items": {"$ref": "urn:nodeskclaw:knowledge:frontend:v1:quality-snapshot"},
                }
            },
            ["history"],
        ),
    ),
    "artifact": _schema_doc(
        "artifact",
        "KnowledgeArtifact",
        _obj(
            {
                "id": {"type": "string"},
                "knowledge_base_id": {"type": "string"},
                "artifact_type": {"type": "string"},
                "provider": {"type": "string"},
                "scope": {"type": "string"},
                "source_file_id": NULLABLE_STRING,
                "file_version_id": NULLABLE_STRING,
                "status": {"type": "string"},
                "version": {"type": "integer"},
                "active_revision_id": NULLABLE_STRING,
                "input_manifest_hash": NULLABLE_STRING,
                "last_built_at": NULLABLE_STRING,
                "last_validated_at": NULLABLE_STRING,
                "last_error": NULLABLE_STRING,
            },
            ["id", "knowledge_base_id", "artifact_type", "status"],
        ),
    ),
    "artifact-build-request": _schema_doc(
        "artifact-build-request",
        "ArtifactBuildRequest",
        _obj(
            {
                "artifact_type": {"type": "string", "minLength": 1},
                "source_file_id": NULLABLE_STRING,
                "file_version_id": NULLABLE_STRING,
            },
            ["artifact_type"],
        ),
    ),
    "artifact-build-accepted": _schema_doc(
        "artifact-build-accepted",
        "ArtifactBuildAccepted",
        _obj(
            {
                "artifact_id": {"type": "string"},
                "artifact_type": {"type": "string"},
                "status": {"type": "string"},
                "build_job_id": NULLABLE_STRING,
                "input_manifest_hash": NULLABLE_STRING,
            },
            ["artifact_id", "artifact_type", "status"],
        ),
    ),
    "artifact-content": _schema_doc(
        "artifact-content",
        "ArtifactContent",
        _obj(
            {"artifact_type": {"type": "string"}, "content": True},
            ["artifact_type", "content"],
            extra=True,
        ),
    ),
}


def _ep(
    endpoint_id: str,
    method: str,
    path: str,
    *,
    stability: str,
    surface: str,
    response: str | None,
    request: str | None = None,
    async_op: bool = False,
    auth: str | None = "bearer",
    success_status: int = 200,
    poll: str | None = None,
    feature: str | None = None,
    notes: str | None = None,
    content_type: str = "application/json",
    envelope: str = "api",
) -> dict:
    item = {
        "id": endpoint_id,
        "method": method,
        "path": path,
        "stability": stability,
        "surface": surface,
        "async": async_op,
        "auth": auth,
        "success_status": success_status,
        "request": request,
        "response": response,
        "content_type": content_type,
        "envelope": envelope,
    }
    if poll:
        item["poll"] = poll
    if feature:
        item["feature"] = feature
    if notes:
        item["notes"] = notes
    return item


MATRIX: list[dict] = [
    _ep("H01", "GET", "/health/ready", stability="stable", surface="bootstrap", response="health-ready", auth=None, envelope="raw", notes="environment readiness; not product capability detail"),
    _ep("KB01", "GET", "/api/v2/knowledge-bases", stability="stable", surface="knowledge-base", response="knowledge-base"),
    _ep("KB02", "POST", "/api/v2/knowledge-bases", stability="stable", surface="knowledge-base", request="knowledge-base-create", response="knowledge-base"),
    _ep("KB03", "GET", "/api/v2/knowledge-bases/{kb_id}", stability="stable", surface="knowledge-base", response="knowledge-base"),
    _ep("KB04", "PATCH", "/api/v2/knowledge-bases/{kb_id}", stability="stable", surface="knowledge-base", request="knowledge-base-update", response="knowledge-base"),
    _ep("KB05", "DELETE", "/api/v1/knowledge-bases/{kb_id}", stability="compatibility", surface="knowledge-base", response=None),
    _ep("KB06", "GET", "/api/v1/knowledge-bases/{kb_id}/acl", stability="compatibility", surface="acl", response="acl"),
    _ep("KB07", "POST", "/api/v1/knowledge-bases/{kb_id}/acl", stability="compatibility", surface="acl", request="acl-create", response="acl"),
    _ep("KB08", "DELETE", "/api/v1/knowledge-bases/{kb_id}/acl/{acl_id}", stability="compatibility", surface="acl", response=None),
    _ep("KB09", "GET", "/api/v1/knowledge-bases/{kb_id}/metadata-schema", stability="compatibility", surface="knowledge-base", response="metadata-schema"),
    _ep("KB10", "PUT", "/api/v1/knowledge-bases/{kb_id}/metadata-schema", stability="compatibility", surface="knowledge-base", request="metadata-schema", response="metadata-schema"),
    _ep("F01", "GET", "/api/v1/knowledge-bases/{kb_id}/files", stability="compatibility", surface="documents", response="source-file"),
    _ep("F02", "POST", "/api/v1/knowledge-bases/{kb_id}/files", stability="compatibility", surface="documents", response="upload-accepted", async_op=True, poll="GET /api/v1/ingestion-jobs/{job_id}", content_type="multipart/form-data"),
    _ep("F03", "GET", "/api/v1/source-files/{source_file_id}", stability="compatibility", surface="documents", response="source-file"),
    _ep("F04", "GET", "/api/v1/source-files/{source_file_id}/versions", stability="compatibility", surface="documents", response="source-file-version"),
    _ep("F05", "POST", "/api/v1/source-files/{source_file_id}/versions", stability="compatibility", surface="documents", response="upload-accepted", async_op=True, poll="GET /api/v1/ingestion-jobs/{job_id}", content_type="multipart/form-data"),
    _ep("F06", "POST", "/api/v1/source-files/{source_file_id}/versions/{version_id}/activate", stability="compatibility", surface="documents", response="source-file"),
    _ep("F07", "POST", "/api/v1/source-files/{source_file_id}/archive", stability="compatibility", surface="documents", response="source-file"),
    _ep("F08", "POST", "/api/v1/source-files/{source_file_id}/unarchive", stability="compatibility", surface="documents", response="source-file"),
    _ep("F09", "POST", "/api/v1/source-files/{source_file_id}/reparse", stability="compatibility", surface="documents", response="ingestion-job", async_op=True, poll="GET /api/v1/ingestion-jobs/{job_id}"),
    _ep("F10", "GET", "/api/v1/source-files/{source_file_id}/download", stability="compatibility", surface="documents", response=None, content_type="application/octet-stream", envelope="binary"),
    _ep("F11", "GET", "/api/v1/source-files/{source_file_id}/acl", stability="compatibility", surface="acl", response="acl"),
    _ep("F12", "POST", "/api/v1/source-files/{source_file_id}/acl", stability="compatibility", surface="acl", request="acl-create", response="acl"),
    _ep("F13", "DELETE", "/api/v1/source-files/{source_file_id}/acl/{acl_id}", stability="compatibility", surface="acl", response=None),
    _ep("F14", "DELETE", "/api/v1/source-files/{source_file_id}", stability="compatibility", surface="documents", response=None),
    _ep("J01", "GET", "/api/v1/ingestion-jobs/{job_id}", stability="stable-compat", surface="ingestion", response="ingestion-job"),
    _ep("J02", "POST", "/api/v1/ingestion-jobs/{job_id}/retry", stability="stable-compat", surface="ingestion", response="ingestion-job", async_op=True, poll="GET /api/v1/ingestion-jobs/{job_id}"),
    _ep("J03", "POST", "/api/v1/ingestion-jobs/{job_id}/cancel", stability="stable-compat", surface="ingestion", response="ingestion-job"),
    _ep("S01", "GET", "/api/v2/knowledge-sets", stability="stable", surface="knowledge-set", response="knowledge-set"),
    _ep("S02", "POST", "/api/v2/knowledge-sets", stability="stable", surface="knowledge-set", request="knowledge-set-create", response="knowledge-set"),
    _ep("S03", "GET", "/api/v2/knowledge-sets/{set_id}", stability="stable", surface="knowledge-set", response="knowledge-set"),
    _ep("S04", "PATCH", "/api/v2/knowledge-sets/{set_id}", stability="stable", surface="knowledge-set", request="knowledge-set-update", response="knowledge-set"),
    _ep("S05", "POST", "/api/v2/knowledge-sets/{set_id}/knowledge-bases", stability="stable", surface="knowledge-set", request="knowledge-set-bind", response=None),
    _ep("S06", "DELETE", "/api/v2/knowledge-sets/{set_id}/knowledge-bases/{kb_id}", stability="stable", surface="knowledge-set", response=None),
    _ep("P01", "GET", "/api/v1/knowledge-sets/{set_id}/retrieval-profiles", stability="compatibility", surface="retrieval-profile", response="retrieval-profile"),
    _ep("P02", "POST", "/api/v1/knowledge-sets/{set_id}/retrieval-profiles", stability="compatibility", surface="retrieval-profile", request="retrieval-profile-create", response="retrieval-profile"),
    _ep("P06", "GET", "/api/v1/retrieval-profiles/{profile_id}", stability="compatibility", surface="retrieval-profile", response="retrieval-profile"),
    _ep("P03", "PATCH", "/api/v1/retrieval-profiles/{profile_id}", stability="compatibility", surface="retrieval-profile", request="retrieval-profile-update", response="retrieval-profile"),
    _ep("P04", "POST", "/api/v1/retrieval-profiles/{profile_id}/publish", stability="compatibility", surface="retrieval-profile", response="retrieval-profile"),
    _ep("P05", "POST", "/api/v1/retrieval-profiles/{profile_id}/rollback", stability="compatibility", surface="retrieval-profile", request="retrieval-profile-rollback", response="retrieval-profile"),
    _ep("E01", "GET", "/api/v2/knowledge-bases/{kb_id}/indexes", stability="stable", surface="engineering", response="index-state-map"),
    _ep("E02", "GET", "/api/v2/knowledge-bases/{kb_id}/build-profile", stability="stable", surface="engineering", response="build-profile-view"),
    _ep("E03", "PUT", "/api/v2/knowledge-bases/{kb_id}/build-profile", stability="stable", surface="engineering", request="build-profile-update", response="build-profile-view"),
    _ep("E04", "POST", "/api/v2/knowledge-bases/{kb_id}/builds", stability="stable", surface="engineering", request="trigger-builds", response="build-job-list", async_op=True, poll="GET /api/v2/builds/{build_id}"),
    _ep("E05", "GET", "/api/v2/builds/{build_id}", stability="stable", surface="engineering", response="build-job"),
    _ep("E06", "POST", "/api/v2/builds/{build_id}/retry", stability="stable", surface="engineering", response="build-job", async_op=True, poll="GET /api/v2/builds/{build_id}"),
    _ep("A01", "GET", "/api/v2/applications", stability="stable", surface="application", response="application"),
    _ep("A02", "POST", "/api/v2/applications", stability="stable", surface="application", request="application-create", response="application"),
    _ep("A03", "GET", "/api/v2/applications/{application_id}", stability="stable", surface="application", response="application"),
    _ep("A04", "PATCH", "/api/v2/applications/{application_id}", stability="stable", surface="application", request="application-update", response="application"),
    _ep("A05", "GET", "/api/v2/applications/{application_id}/readiness", stability="stable", surface="application", response="application-readiness"),
    _ep("A06", "POST", "/api/v2/applications/{application_id}/knowledge-sets", stability="stable", surface="application", request="application-bind-set", response=None),
    _ep("A07", "DELETE", "/api/v2/applications/{application_id}/knowledge-sets/{set_id}", stability="stable", surface="application", response=None),
    _ep("A08", "GET", "/api/v2/applications/{application_id}/retrieval-policy-revisions", stability="stable", surface="application-policy", response="retrieval-policy-revision"),
    _ep("A09", "POST", "/api/v2/applications/{application_id}/retrieval-policy-revisions", stability="stable", surface="application-policy", request="retrieval-policy-revision-create", response="retrieval-policy-revision"),
    _ep("A10", "POST", "/api/v2/applications/{application_id}/retrieval-policy-revisions/{revision_id}/publish", stability="stable", surface="application-policy", response="retrieval-policy-revision"),
    _ep("R01", "GET", "/api/v2/applications/{application_id}/releases", stability="stable", surface="release", response="release"),
    _ep("R02", "POST", "/api/v2/applications/{application_id}/releases", stability="stable", surface="release", request="release-create", response="release"),
    _ep("R03", "GET", "/api/v2/applications/{application_id}/releases/{release_id}", stability="stable", surface="release", response="release"),
    _ep("R04", "POST", "/api/v2/applications/{application_id}/releases/{release_id}/validate", stability="stable", surface="release", response="release", async_op=True, success_status=202, poll="GET /api/v2/builds/{validation_job_id}"),
    _ep("R05", "POST", "/api/v2/applications/{application_id}/releases/{release_id}/retire", stability="stable", surface="release", response="release"),
    _ep("R06", "GET", "/api/v2/applications/{application_id}/channels", stability="stable", surface="release", response="channel"),
    _ep("R07", "POST", "/api/v2/applications/{application_id}/channels/{channel}/promote", stability="stable", surface="release", request="release-promote", response="channel"),
    _ep("R08", "POST", "/api/v2/applications/{application_id}/channels/{channel}/rollback", stability="stable", surface="release", response="channel"),
    _ep("R09", "POST", "/api/v2/applications/{application_id}/publish", stability="stable", surface="release", request="application-publish", response="application", async_op=True, success_status=202),
    _ep("R10", "POST", "/api/v2/applications/{application_id}/disable", stability="stable", surface="application", response="application"),
    _ep("Q01", "POST", "/api/v2/applications/{application_id}/retrieval", stability="stable", surface="retrieval", request="application-retrieval-request", response="retrieval-response"),
    _ep("Q02", "POST", "/api/v2/retrieval/playground", stability="stable", surface="retrieval-debug", request="playground-request", response="playground-response", notes="trace/query_analysis fields are not frozen; frontend must not depend on debug internals"),
    _ep("Q03", "GET", "/api/v2/evidence/{evidence_id}", stability="stable", surface="evidence", response="evidence"),
    _ep("O01", "GET", "/api/v2/knowledge-bases/{kb_id}/quality", stability="optional", surface="quality", response="quality-snapshot", feature="KNOWLEDGE_V23_QUALITY_ENABLED"),
    _ep("O02", "GET", "/api/v2/applications/{application_id}/quality", stability="optional", surface="quality", response="quality-snapshot", feature="KNOWLEDGE_V23_QUALITY_ENABLED"),
    _ep("O06", "GET", "/api/v2/knowledge-bases/{kb_id}/quality/history", stability="optional", surface="quality", response="quality-history", feature="KNOWLEDGE_V23_QUALITY_ENABLED"),
    _ep("O03", "GET", "/api/v2/knowledge-bases/{kb_id}/artifacts", stability="optional", surface="artifact", response="artifact", feature="KNOWLEDGE_V23_ARTIFACTS_ENABLED"),
    _ep("O07", "GET", "/api/v2/knowledge-bases/{kb_id}/artifacts/{artifact_type}", stability="optional", surface="artifact", response="artifact", feature="KNOWLEDGE_V23_ARTIFACTS_ENABLED"),
    _ep("O04", "POST", "/api/v2/knowledge-bases/{kb_id}/artifacts/builds", stability="optional", surface="artifact", request="artifact-build-request", response="artifact-build-accepted", async_op=True, poll="GET /api/v2/builds/{build_job_id}", feature="KNOWLEDGE_V23_ARTIFACTS_ENABLED"),
    _ep("O08", "GET", "/api/v2/artifacts/{artifact_id}", stability="optional", surface="artifact", response="artifact", feature="KNOWLEDGE_V23_ARTIFACTS_ENABLED"),
    _ep("O05", "GET", "/api/v2/artifacts/{artifact_id}/content", stability="optional", surface="artifact", response="artifact-content", feature="KNOWLEDGE_V23_ARTIFACTS_ENABLED"),
]

FIXTURE_SCHEMA = {
    "error-release-conflict.json": "error-response",
    "error-retrieval-unavailable.json": "error-response",
    "retrieval-success.json": ("api-response", "retrieval-response"),
    "retrieval-empty.json": ("api-response", "retrieval-response"),
    "ingestion-active.json": ("api-response", "ingestion-job"),
    "build-completed.json": ("api-response", "build-job"),
    "release-validating.json": ("api-response", "release"),
    "indexes-ready.json": ("api-response", "index-state-map"),
    "upload-accepted.json": ("api-response", "upload-accepted"),
    "evidence-resolved.json": ("api-response", "evidence"),
}

NEGATIVE_FIXTURES = {
    "invalid-chunk-provider-ids.json": "evidence-item",
}
