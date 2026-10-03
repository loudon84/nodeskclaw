from __future__ import annotations

from fastapi.responses import JSONResponse


class RemoteAcpError(Exception):
    def __init__(self, error_code: str, status_code: int, message_key: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.message_key = message_key
        self.message = message

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={
                "error_code": self.error_code,
                "message_key": self.message_key,
                "message": self.message,
            },
        )


AUTH_REQUIRED = RemoteAcpError(
    "REMOTE_ACP_AUTH_REQUIRED", 401, "errors.remote_acp.auth_required", "需要登录"
)
ORG_FORBIDDEN = RemoteAcpError(
    "REMOTE_ACP_ORG_FORBIDDEN", 403, "errors.remote_acp.org_forbidden", "组织无权访问"
)
EXPERT_NOT_FOUND = RemoteAcpError(
    "REMOTE_ACP_EXPERT_NOT_FOUND", 404, "errors.remote_acp.expert_not_found", "远程专家不存在"
)
EXPERT_FORBIDDEN = RemoteAcpError(
    "REMOTE_ACP_EXPERT_FORBIDDEN", 403, "errors.remote_acp.expert_forbidden", "缺少专家调用权限"
)
EXPERT_UNAVAILABLE = RemoteAcpError(
    "REMOTE_ACP_EXPERT_UNAVAILABLE", 503, "errors.remote_acp.expert_unavailable", "专家运行时不可用"
)
RUNTIME_UNAVAILABLE = RemoteAcpError(
    "REMOTE_ACP_RUNTIME_UNAVAILABLE", 503, "errors.remote_acp.runtime_unavailable", "执行平面不可用"
)
ROUTE_FAILED = RemoteAcpError(
    "REMOTE_ACP_ROUTE_FAILED", 503, "errors.remote_acp.route_failed", "路由失败"
)
TRANSPORT_UNSUPPORTED = RemoteAcpError(
    "REMOTE_ACP_TRANSPORT_UNSUPPORTED", 400, "errors.remote_acp.transport_unsupported", "不支持的传输协议"
)
ARTIFACT_DENIED = RemoteAcpError(
    "ARTIFACT_ACCESS_DENIED", 403, "errors.remote_acp.artifact_access_denied", "产物访问被拒绝"
)
