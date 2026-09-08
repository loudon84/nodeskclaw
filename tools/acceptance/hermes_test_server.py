#!/usr/bin/env python3
"""Native Run Hermes test double for acceptance compose."""

from __future__ import annotations

import argparse
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

NATIVE_VERSION = "v2026.8.31"
NATIVE_PACKAGE = "0.21.0"
NATIVE_FEATURES = [
    "run_submission",
    "run_status",
    "run_events_sse",
    "run_stop",
    "run_approval_response",
    "approval_events",
]


def _api_key() -> str:
    return os.getenv("HERMES_TEST_API_KEY", "").strip()


# @lat: [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture#Native Fixture Protocol]]
class HermesHandler(BaseHTTPRequestHandler):
    _runs: dict[str, dict[str, Any]] = {}
    _lock = threading.Lock()

    def log_message(self, format: str, *args) -> None:
        return

    def _route(self) -> str:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        return path

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _send_json(self, status: int, payload: dict[str, Any] | list[Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _unauthorized(self) -> bool:
        expected = _api_key()
        if not expected:
            return False
        header = self.headers.get("Authorization", "")
        if header == f"Bearer {expected}":
            return False
        self._send_json(401, {"error": "unauthorized"})
        return True

    def _get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            return dict(run) if run else None

    def _update_run(self, run_id: str, **fields: Any) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                return None
            run.update(fields)
            return dict(run)

    def _create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        run_id = f"run-{uuid.uuid4().hex[:16]}"
        text = " ".join(
            [
                str(payload.get("input") or ""),
                str(payload.get("instructions") or ""),
            ]
        )
        hold = "acceptance-hold" in text
        wait = threading.Event()
        record: dict[str, Any] = {
            "id": run_id,
            "status": "running" if hold else "completed",
            "output": "acceptance-ok",
            "hold": hold,
            "wait": wait,
            "approval": None,
        }
        with self._lock:
            self._runs[run_id] = record
        return {"id": run_id, "status": record["status"], "output": record["output"]}

    def _write_sse(self, event_name: str, data: dict[str, Any]) -> None:
        chunk = f"event: {event_name}\ndata: {json.dumps(data)}\n\n".encode("utf-8")
        self.wfile.write(chunk)
        self.wfile.flush()

    def do_POST(self) -> None:
        path = self._route()
        if path == "/v1/chat/completions":
            self.send_error(404, "not found")
            return
        if self._unauthorized():
            return
        if path == "/v1/runs":
            created = self._create_run(self._read_json())
            self._send_json(200, created)
            return
        parts = path.split("/")
        if len(parts) == 5 and parts[1] == "v1" and parts[2] == "runs":
            run_id = parts[3]
            action = parts[4]
            run = self._get_run(run_id)
            if not run:
                self._send_json(404, {"error": "run_not_found"})
                return
            if action == "stop":
                updated = self._update_run(run_id, status="cancelled")
                wait = None
                with self._lock:
                    stored = self._runs.get(run_id)
                    if stored:
                        wait = stored.get("wait")
                if isinstance(wait, threading.Event):
                    wait.set()
                self._send_json(200, {"id": run_id, "status": (updated or {}).get("status")})
                return
            if action == "approval":
                body = self._read_json()
                choice = str(body.get("choice") or "").strip().lower()
                status = "completed" if choice in {"once", "approve", "approved", "allow"} else "failed"
                self._update_run(run_id, status=status, approval=choice)
                wait = None
                with self._lock:
                    stored = self._runs.get(run_id)
                    if stored:
                        wait = stored.get("wait")
                if isinstance(wait, threading.Event):
                    wait.set()
                self._send_json(200, {"id": run_id, "status": status, "choice": choice})
                return
        self.send_error(404, "not found")

    def do_GET(self) -> None:
        path = self._route()
        if path in {"/health", "/healthz", "/"}:
            self._send_json(200, {"status": "ok", "version": NATIVE_VERSION, "package": NATIVE_PACKAGE})
            return
        if path == "/v1/chat/completions":
            self.send_error(404, "not found")
            return
        if self._unauthorized():
            return
        if path == "/v1/capabilities":
            self._send_json(
                200,
                {
                    "version": NATIVE_VERSION,
                    "package": NATIVE_PACKAGE,
                    "features": list(NATIVE_FEATURES),
                },
            )
            return
        if path == "/v1/models":
            self._send_json(200, {"data": [{"id": "hermes", "object": "model"}]})
            return
        parts = path.split("/")
        if len(parts) >= 4 and parts[1] == "v1" and parts[2] == "runs":
            run_id = parts[3]
            run = self._get_run(run_id)
            if not run:
                self._send_json(404, {"error": "run_not_found"})
                return
            if len(parts) == 4:
                self._send_json(
                    200,
                    {
                        "id": run_id,
                        "status": run.get("status"),
                        "output": run.get("output"),
                    },
                )
                return
            if len(parts) == 5 and parts[4] == "events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                status = str(run.get("status") or "")
                if run.get("hold") and status == "running":
                    wait = None
                    with self._lock:
                        stored = self._runs.get(run_id)
                        if stored:
                            wait = stored.get("wait")
                    if isinstance(wait, threading.Event):
                        wait.wait(timeout=120)
                    latest = self._get_run(run_id) or run
                    status = str(latest.get("status") or status)
                self._write_sse(
                    "assistant.message",
                    {"type": "assistant.message", "delta": "acceptance-ok"},
                )
                event_name = "run.completed"
                if status in {"cancelled", "canceled"}:
                    event_name = "run.cancelled"
                elif status in {"failed", "error"}:
                    event_name = "run.failed"
                self._write_sse(
                    event_name,
                    {
                        "type": event_name,
                        "status": status or "completed",
                        "output": "acceptance-ok",
                    },
                )
                return
        self.send_error(404, "not found")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes Native acceptance test double")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), HermesHandler)
    print(f"hermes test server listening on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
