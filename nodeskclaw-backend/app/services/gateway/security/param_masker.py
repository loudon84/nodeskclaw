import logging

logger = logging.getLogger(__name__)

_DEFAULT_SENSITIVE_NAMES = {"password", "token", "secret", "key", "credential", "api_key", "private_key"}


class ParamMasker:
    @staticmethod
    def mask_params(
        params: dict | list | None,
        sensitive_names: list[str] | None = None,
    ) -> dict | list | None:
        if params is None:
            return None

        names_set = set()
        for name in (sensitive_names or list(_DEFAULT_SENSITIVE_NAMES)):
            names_set.add(name.lower())

        try:
            return ParamMasker._mask_recursive(params, names_set)
        except Exception:
            logger.warning("参数脱敏失败，回退为空", exc_info=True)
            return None

    @staticmethod
    def _mask_recursive(obj: dict | list, sensitive_names: set[str]) -> dict | list:
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k.lower() in sensitive_names:
                    result[k] = "***REDACTED***"
                elif isinstance(v, (dict, list)):
                    result[k] = ParamMasker._mask_recursive(v, sensitive_names)
                else:
                    result[k] = v
            return result
        elif isinstance(obj, list):
            return [ParamMasker._mask_recursive(item, sensitive_names) if isinstance(item, (dict, list)) else item for item in obj]
        return obj
