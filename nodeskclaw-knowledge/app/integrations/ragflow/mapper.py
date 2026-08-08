"""Map RAGFlow transport errors to RagflowError."""

from app.integrations.ragflow.exceptions import RagflowError


def map_ragflow_payload(code: int, message: str) -> RagflowError:
    lower = (message or "").lower()
    if code in {101, 102} and ("own the dataset" in lower or "unauthorized" in lower):
        return RagflowError(
            message="RAGFlow 拒绝访问",
            ragflow_code=code,
            message_key="errors.knowledge.ragflow_forbidden",
            status_code=403,
        )
    if code == 102:
        return RagflowError(
            message="RAGFlow 请求参数错误",
            ragflow_code=code,
            message_key="errors.knowledge.ragflow_bad_request",
            status_code=400,
        )
    return RagflowError(
        message="RAGFlow 调用失败",
        ragflow_code=code,
        message_key="errors.knowledge.ragflow_error",
        status_code=502,
    )


def map_transport_error(exc: Exception) -> RagflowError:
    return RagflowError(
        message="RAGFlow 不可用",
        ragflow_code=None,
        message_key="errors.knowledge.ragflow_unavailable",
        status_code=502,
    )
