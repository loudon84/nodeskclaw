import pytest
from app.services.gateway.security.injection_guard import InjectionGuard
from app.core.exceptions import AppException


class TestInjectionGuard:
    def test_valid_tool_name(self):
        InjectionGuard.check_tool_name("file_read")
        InjectionGuard.check_tool_name("my-tool.v2")

    def test_invalid_tool_name(self):
        with pytest.raises(AppException) as exc_info:
            InjectionGuard.check_tool_name("../../etc/passwd")
        assert exc_info.value.error_code == 40021

    def test_path_traversal_in_params(self):
        with pytest.raises(AppException) as exc_info:
            InjectionGuard.check_params({"path": "../../../etc/passwd"})
        assert exc_info.value.error_code == 40020

    def test_command_injection_in_params(self):
        with pytest.raises(AppException) as exc_info:
            InjectionGuard.check_params({"cmd": "ls; rm -rf /"})
        assert exc_info.value.error_code == 40022

    def test_safe_params(self):
        InjectionGuard.check_params({"name": "test", "value": "hello"})

    def test_none_params(self):
        InjectionGuard.check_params(None)
