"""Correlation ID + HTTP metrics middleware."""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_context import (
    REQUEST_ID_HEADER,
    ensure_request_id,
    reset_request_id,
    set_request_id,
)
from app.services import metrics_service

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = ensure_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            if not request.url.path.startswith("/metrics"):
                metrics_service.observe_http_request(
                    method=request.method,
                    path=request.url.path,
                    status=response.status_code,
                )
            if response.status_code >= 400:
                logger.error(
                    "frontend_http_error method=%s path=%s status=%s client=%s",
                    request.method,
                    request.url.path,
                    response.status_code,
                    request.client.host if request.client else "-",
                )
            return response
        except Exception:
            metrics_service.observe_http_request(
                method=request.method,
                path=request.url.path,
                status=500,
            )
            raise
        finally:
            reset_request_id(token)
