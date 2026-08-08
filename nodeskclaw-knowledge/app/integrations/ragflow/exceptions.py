"""RAGFlow adapter exceptions."""


class RagflowError(Exception):
    def __init__(
        self,
        message: str,
        *,
        ragflow_code: int | None = None,
        message_key: str = "errors.knowledge.ragflow_error",
        status_code: int = 502,
    ):
        super().__init__(message)
        self.message = message
        self.ragflow_code = ragflow_code
        self.message_key = message_key
        self.status_code = status_code
