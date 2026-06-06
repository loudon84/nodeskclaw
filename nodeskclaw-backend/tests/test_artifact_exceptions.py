import pytest
from app.core.exceptions import (
    ArtifactNotFoundError,
    ArtifactFileNotFoundError,
    ArtifactForbiddenError,
    ArtifactScopeInvalidError,
    ArtifactTokenExpiredError,
    ArtifactPreviewUnsupportedError,
    ArtifactBatchSizeExceededError,
    ArtifactAlreadyGrantedError,
    ArtifactShareDisabledError,
)


class TestArtifactExceptions:
    def test_artifact_not_found(self):
        exc = ArtifactNotFoundError()
        assert exc.status_code == 404
        assert exc.error_code == 40472
        assert exc.message_key == "errors.artifact.not_found"

    def test_artifact_file_not_found(self):
        exc = ArtifactFileNotFoundError()
        assert exc.status_code == 404
        assert exc.error_code == 40473

    def test_artifact_forbidden(self):
        exc = ArtifactForbiddenError()
        assert exc.status_code == 403
        assert exc.error_code == 40301

    def test_scope_invalid(self):
        exc = ArtifactScopeInvalidError()
        assert exc.status_code == 400
        assert exc.error_code == 40001

    def test_token_expired(self):
        exc = ArtifactTokenExpiredError()
        assert exc.status_code == 410
        assert exc.error_code == 41001

    def test_preview_unsupported(self):
        exc = ArtifactPreviewUnsupportedError()
        assert exc.status_code == 415
        assert exc.error_code == 41501

    def test_batch_size_exceeded(self):
        exc = ArtifactBatchSizeExceededError()
        assert exc.status_code == 413
        assert exc.error_code == 41301

    def test_already_granted(self):
        exc = ArtifactAlreadyGrantedError()
        assert exc.status_code == 400
        assert exc.error_code == 40002

    def test_share_disabled(self):
        exc = ArtifactShareDisabledError()
        assert exc.status_code == 403
        assert exc.error_code == 40302
