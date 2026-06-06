from app.services.gateway.security.param_masker import ParamMasker


class TestParamMasker:
    def test_mask_simple(self):
        result = ParamMasker.mask_params({"password": "secret123", "name": "test"})
        assert result["password"] == "***REDACTED***"
        assert result["name"] == "test"

    def test_mask_nested(self):
        result = ParamMasker.mask_params({
            "config": {"api_key": "abc123", "host": "example.com"}
        })
        assert result["config"]["api_key"] == "***REDACTED***"
        assert result["config"]["host"] == "example.com"

    def test_mask_list(self):
        result = ParamMasker.mask_params([
            {"token": "t1", "value": "v1"},
            {"token": "t2", "value": "v2"},
        ])
        assert result[0]["token"] == "***REDACTED***"
        assert result[1]["token"] == "***REDACTED***"

    def test_mask_none_input(self):
        assert ParamMasker.mask_params(None) is None

    def test_mask_case_insensitive(self):
        result = ParamMasker.mask_params({"Password": "x", "TOKEN": "y"})
        assert result["Password"] == "***REDACTED***"
        assert result["TOKEN"] == "***REDACTED***"

    def test_custom_sensitive_names(self):
        result = ParamMasker.mask_params({"my_secret": "x", "name": "y"}, ["my_secret"])
        assert result["my_secret"] == "***REDACTED***"
        assert result["name"] == "y"
