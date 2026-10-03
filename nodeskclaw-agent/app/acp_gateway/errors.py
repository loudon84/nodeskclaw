from __future__ import annotations

from typing import Any


class AcpGatewayError(Exception):
    def __init__(self, error_code: str, message: str, *, http_status: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.message_key = f"errors.acp.{error_code.lower()}"
        self.http_status = http_status

    def to_jsonrpc(self, request_id: Any = None) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32000,
                "message": self.message,
                "data": {
                    "error_code": self.error_code,
                    "message_key": self.message_key,
                },
            },
        }

    def to_http(self) -> dict[str, str]:
        return {
            "error_code": self.error_code,
            "message_key": self.message_key,
            "message": self.message,
        }
