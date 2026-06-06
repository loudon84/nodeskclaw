import re
from app.core.exceptions import AppException

_TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{1,128}$")
_PATH_TRAVERSAL_PATTERNS = re.compile(r"(\.\./|\.\.\\|/etc/|\\etc\\)")
_SHELL_META_CHARS = re.compile(r"(;\s*|\|\s*|\$\(|`)")


class InjectionGuard:
    @staticmethod
    def check_tool_name(name: str) -> None:
        if not _TOOL_NAME_PATTERN.match(name):
            raise AppException(
                code=40021, message=f"工具名格式无效: {name}", status_code=400,
                error_code=40021, message_key="errors.mcp.invalid_tool_name",
            )

    @staticmethod
    def check_params(params: dict | list | None) -> None:
        if params is None:
            return
        InjectionGuard._check_recursive(params)

    @staticmethod
    def _check_recursive(obj: dict | list) -> None:
        if isinstance(obj, dict):
            for v in obj.values():
                if isinstance(v, str):
                    InjectionGuard._check_string(v)
                elif isinstance(v, (dict, list)):
                    InjectionGuard._check_recursive(v)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, str):
                    InjectionGuard._check_string(item)
                elif isinstance(item, (dict, list)):
                    InjectionGuard._check_recursive(item)

    @staticmethod
    def _check_string(s: str) -> None:
        if _PATH_TRAVERSAL_PATTERNS.search(s):
            raise AppException(
                code=40020, message="检测到路径遍历序列", status_code=400,
                error_code=40020, message_key="errors.mcp.path_traversal",
            )
        if _SHELL_META_CHARS.search(s):
            raise AppException(
                code=40022, message="检测到命令注入字符", status_code=400,
                error_code=40022, message_key="errors.mcp.command_injection",
            )
