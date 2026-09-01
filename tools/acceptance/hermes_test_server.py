#!/usr/bin/env python3
"""Minimal OpenAI-compatible Hermes test double for acceptance compose."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class HermesHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self.send_error(404, "not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(length)
        payload = {
            "id": "chatcmpl-acceptance",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "acceptance-ok"},
                    "finish_reason": "stop",
                }
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/health", "/healthz", "/"}:
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404, "not found")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes acceptance test double")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), HermesHandler)
    print(f"hermes test server listening on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
