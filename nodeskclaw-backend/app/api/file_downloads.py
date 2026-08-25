"""Shared file download response helpers."""

from urllib.parse import quote

from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.services import storage_service


def content_disposition_attachment(filename: str) -> str:
    encoded = quote(filename or "download", safe="")
    return f"attachment; filename*=UTF-8''{encoded}"


async def build_storage_download_response(
    *,
    storage_key: str,
    filename: str,
    content_type: str,
    range_header: str | None = None,
) -> Response | StreamingResponse:
    try:
        download = await storage_service.get_download_stream(storage_key, range_header)
    except storage_service.DownloadRangeNotSatisfiableError as exc:
        return JSONResponse(
            status_code=416,
            content={
                "error_code": 41600,
                "message_key": "errors.upload.invalid_download_range",
                "message": "下载范围无效",
            },
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes */{exc.size}",
            },
        )

    resolved = download.range
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": content_disposition_attachment(filename),
        "Content-Length": str(resolved.length),
    }
    status_code = 206 if resolved.is_partial else 200
    if resolved.is_partial:
        headers["Content-Range"] = resolved.content_range

    return StreamingResponse(
        download.chunks,
        status_code=status_code,
        media_type=content_type or "application/octet-stream",
        headers=headers,
    )
