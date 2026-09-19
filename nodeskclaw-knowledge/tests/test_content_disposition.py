"""Content-Disposition header encoding for download responses."""

from urllib.parse import quote

from app.core.http_headers import content_disposition_attachment


def test_ascii_filename_uses_quoted_filename():
    header = content_disposition_attachment("report.png")
    assert header == 'attachment; filename="report.png"'


def test_non_ascii_filename_uses_rfc5987():
    header = content_disposition_attachment("产品说明.png")
    assert "filename=" in header
    assert "filename*=UTF-8''" in header
    assert quote("产品说明.png", safe="") in header
    header.encode("latin-1")


def test_empty_filename_falls_back_to_download():
    header = content_disposition_attachment("")
    assert header == 'attachment; filename="download"'
    header.encode("latin-1")
