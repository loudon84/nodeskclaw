"""LLM Proxy errors."""


class LlmProxyError(Exception):
    def __init__(self, message: str, *, message_key: str = "errors.knowledge.llm_proxy_error"):
        super().__init__(message)
        self.message = message
        self.message_key = message_key
