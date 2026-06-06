from app.core.exceptions import AppException


_DEFAULT_METHOD_WHITELIST = ["tools/list", "tools/call", "resources/list", "resources/read", "prompts/list"]


class RequestValidator:
    @staticmethod
    def validate(
        method: str,
        params: dict | None,
        body_size: int,
        max_body_bytes: int = 1048576,
        method_whitelist: list[str] | None = None,
    ) -> None:
        if body_size > max_body_bytes:
            raise AppException(
                code=41300, message="请求体超过大小限制", status_code=413,
                error_code=41300, message_key="errors.mcp.request_too_large",
            )

        if method.startswith("rpc."):
            raise AppException(
                code=40013, message="系统方法禁止调用", status_code=400,
                error_code=40013, message_key="errors.mcp.system_method_forbidden",
            )

        whitelist = method_whitelist or _DEFAULT_METHOD_WHITELIST
        if method not in whitelist:
            raise AppException(
                code=40010, message=f"方法 {method} 不在白名单中", status_code=400,
                error_code=40010, message_key="errors.mcp.method_not_allowed",
            )

        if method == "tools/call":
            if not params or "name" not in params:
                raise AppException(
                    code=40012, message="tools/call 缺少 name 字段", status_code=400,
                    error_code=40012, message_key="errors.mcp.missing_tool_name",
                )

    @staticmethod
    def validate_jsonrpc_version(version: str) -> None:
        if version != "2.0":
            raise AppException(
                code=40011, message=f"不支持的 JSON-RPC 版本: {version}", status_code=400,
                error_code=40011, message_key="errors.mcp.unsupported_jsonrpc_version",
            )
