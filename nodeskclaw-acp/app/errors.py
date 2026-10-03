from __future__ import annotations


class AdapterError(Exception):
    def __init__(self, symbol: str, message: str, *, remote_error_code: str | None = None, run_id: str | None = None):
        super().__init__(message)
        self.symbol = symbol
        self.message = message
        self.remote_error_code = remote_error_code
        self.run_id = run_id

    def to_data(self) -> dict:
        data: dict[str, str] = {"symbol": self.symbol, "message": self.message}
        if self.remote_error_code:
            data["remote_error_code"] = self.remote_error_code
        if self.run_id:
            data["run_id"] = self.run_id
        return data


def auth_required() -> AdapterError:
    return AdapterError("ACP_AUTH_REQUIRED", "需要先登录 NodeSkClaw")


def auth_refresh_failed() -> AdapterError:
    return AdapterError("ACP_AUTH_REFRESH_FAILED", "刷新访问令牌失败")


def profile_invalid(message: str) -> AdapterError:
    return AdapterError("ACP_PROFILE_INVALID", message)


def session_not_found() -> AdapterError:
    return AdapterError("ACP_SESSION_NOT_FOUND", "ACP Session 不存在")


def session_busy() -> AdapterError:
    return AdapterError("ACP_SESSION_BUSY", "当前 Session 已有进行中的 Prompt")


def unsupported_content() -> AdapterError:
    return AdapterError("ACP_PROMPT_UNSUPPORTED_CONTENT", "仅支持文本 Prompt")


def client_mcp_unsupported() -> AdapterError:
    return AdapterError("ACP_CLIENT_MCP_UNSUPPORTED", "v1.6 不支持 Client 本地 MCP")


def protocol_unsupported() -> AdapterError:
    return AdapterError("ACP_PROTOCOL_VERSION_UNSUPPORTED", "仅支持 ACP protocolVersion=1")
