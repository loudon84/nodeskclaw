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


class RagflowUploadUnknownError(RagflowError):
    """Upload may have succeeded on the server but the client saw timeout/unknown outcome."""

    def __init__(
        self,
        message: str = "RAGFlow upload outcome unknown",
        *,
        upload_token: str | None = None,
    ):
        super().__init__(
            message,
            message_key="errors.knowledge.ragflow_upload_unknown",
            status_code=502,
        )
        self.upload_token = upload_token
