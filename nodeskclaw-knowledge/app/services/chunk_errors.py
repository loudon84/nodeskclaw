"""Chunk Thin Gateway domain errors (message_key + HTTP mapping)."""

from __future__ import annotations

from app.core.exceptions import (
    AppException,
    ConflictError,
    NotFoundError,
    NotImplementedAppError,
    ServiceUnavailableError,
)


def chunk_no_active_version() -> ConflictError:
    return ConflictError(
        message="源文件没有激活版本",
        message_key="errors.knowledge.chunk_no_active_version",
        details={"error_code": "KNOWLEDGE_CHUNK_NO_ACTIVE_VERSION"},
    )


def chunk_active_version_invalid() -> ConflictError:
    return ConflictError(
        message="激活版本无效或已删除",
        message_key="errors.knowledge.chunk_active_version_invalid",
        details={"error_code": "KNOWLEDGE_CHUNK_ACTIVE_VERSION_INVALID"},
    )


def chunk_runtime_document_missing() -> ConflictError:
    return ConflictError(
        message="激活版本尚未绑定 Runtime Document",
        message_key="errors.knowledge.chunk_runtime_document_missing",
        details={"error_code": "KNOWLEDGE_CHUNK_RUNTIME_DOCUMENT_MISSING"},
    )


def chunk_runtime_binding_missing() -> ServiceUnavailableError:
    return ServiceUnavailableError(
        message="Knowledge Base Runtime Binding 不可用",
        message_key="errors.knowledge.chunk_runtime_binding_missing",
        details={"error_code": "KNOWLEDGE_CHUNK_RUNTIME_BINDING_MISSING"},
    )


def chunk_provider_unavailable(message: str = "Chunk Provider 不可用") -> ServiceUnavailableError:
    return ServiceUnavailableError(
        message=message,
        message_key="errors.knowledge.chunk_provider_unavailable",
        details={"error_code": "KNOWLEDGE_CHUNK_PROVIDER_UNAVAILABLE"},
    )


def chunk_contract_invalid(message: str = "Chunk Provider 响应不符合契约") -> AppException:
    return AppException(
        code=50200,
        message=message,
        status_code=502,
        message_key="errors.knowledge.chunk_contract_invalid",
        details={"error_code": "KNOWLEDGE_CHUNK_CONTRACT_INVALID"},
    )


def chunk_version_conflict() -> ConflictError:
    return ConflictError(
        message="file_version_id 与当前激活版本不一致",
        message_key="errors.knowledge.chunk_version_conflict",
        details={"error_code": "KNOWLEDGE_CHUNK_VERSION_CONFLICT"},
    )


def chunk_not_found() -> NotFoundError:
    return NotFoundError(
        message="Chunk 不存在或不属于当前文档",
        message_key="errors.knowledge.chunk_not_found",
        details={"error_code": "KNOWLEDGE_CHUNK_NOT_FOUND"},
    )


def chunk_image_not_found() -> NotFoundError:
    return NotFoundError(
        message="Chunk 没有关联图片",
        message_key="errors.knowledge.chunk_image_not_found",
        details={"error_code": "KNOWLEDGE_CHUNK_IMAGE_NOT_FOUND"},
    )


def chunk_image_type_unsupported(message: str = "Chunk 图片类型不受支持") -> AppException:
    return AppException(
        code=41500,
        message=message,
        status_code=415,
        message_key="errors.knowledge.chunk_image_type_unsupported",
        details={"error_code": "KNOWLEDGE_CHUNK_IMAGE_TYPE_UNSUPPORTED"},
    )


def chunk_image_too_large(message: str = "Chunk 图片超过大小限制") -> AppException:
    return AppException(
        code=41300,
        message=message,
        status_code=413,
        message_key="errors.knowledge.chunk_image_too_large",
        details={"error_code": "KNOWLEDGE_CHUNK_IMAGE_TOO_LARGE"},
    )


def chunk_update_unsupported(message: str = "Provider 不支持 Chunk available 更新") -> NotImplementedAppError:
    return NotImplementedAppError(
        message=message,
        message_key="errors.knowledge.chunk_update_unsupported",
        details={"error_code": "KNOWLEDGE_CHUNK_UPDATE_UNSUPPORTED"},
    )


def chunk_mutation_uncertain(message: str = "Chunk 更新结果未知，请重新查询后再试") -> ServiceUnavailableError:
    return ServiceUnavailableError(
        message=message,
        message_key="errors.knowledge.chunk_mutation_uncertain",
        details={"error_code": "KNOWLEDGE_CHUNK_MUTATION_UNCERTAIN"},
    )
