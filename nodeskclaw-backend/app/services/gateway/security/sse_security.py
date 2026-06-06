import logging

logger = logging.getLogger(__name__)


class SSESecurity:
    @staticmethod
    def check_origin(
        origin: str | None,
        allowed_origins: list[str],
        mode: str = "relaxed",
    ) -> bool:
        if mode == "relaxed" and not origin:
            return True

        if mode == "strict" and not origin:
            return False

        if not origin:
            return False

        return origin in allowed_origins

    @staticmethod
    def check_connection_limit(
        global_count: int,
        instance_count: int,
        max_global: int = 500,
        max_per_instance: int = 100,
    ) -> tuple[bool, str | None]:
        if global_count >= max_global:
            return False, "global"
        if instance_count >= max_per_instance:
            return False, "instance"
        return True, None
