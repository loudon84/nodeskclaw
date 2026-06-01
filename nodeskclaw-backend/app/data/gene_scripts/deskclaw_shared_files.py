#!/usr/bin/env python3
"""DeskClaw Shared Files Tool -- manage workspace shared files.

Usage:
  python3 deskclaw_shared_files.py <action> [options]

Actions:
  list_files [--path /]              List files in a directory
  read_file --file-id ID             Read file content (returns base64)
  write_file --file PATH [--filename NAME] [--parent-path /] [--content-type TYPE]
                                     Upload a local file (recommended)
  write_file --content-b64 DATA --filename NAME [--parent-path /] [--content-type TYPE]
                                     Upload base64 content (legacy)
  copy_file --file-id ID [--target-parent-path /] [--target-filename NAME]
                                     Copy a file to another location
  delete_file --file-id ID           Delete a file
  mkdir --name NAME [--parent-path /]  Create a directory
  get_file_url --file-id ID          Get download URL for a file

Environment:
  DESKCLAW_API_URL        Backend API base URL
  DESKCLAW_TOKEN          Instance proxy_token
  DESKCLAW_WORKSPACE_ID   Workspace ID
"""

from __future__ import annotations

import argparse
import sys

from _api_client import api_call, upload_file, _output


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="deskclaw_shared_files", description="DeskClaw Shared Files Tool")
    sub = p.add_subparsers(dest="action", required=True)

    sp = sub.add_parser("list_files", help="List files in a directory")
    sp.add_argument("--path", default="/", help="Parent directory path (default: /)")

    sp = sub.add_parser("read_file", help="Read file content")
    sp.add_argument("--file-id", required=True)

    sp = sub.add_parser("write_file", help="Upload a file")
    group = sp.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Local file path to upload (recommended)")
    group.add_argument("--content-b64", help="File content in base64 encoding (legacy)")
    sp.add_argument("--filename", default=None, help="Target filename (defaults to basename of --file)")
    sp.add_argument("--parent-path", default="/")
    sp.add_argument("--content-type", default=None)

    sp = sub.add_parser("copy_file", help="Copy a file to another location")
    sp.add_argument("--file-id", required=True)
    sp.add_argument("--target-parent-path", default="/")
    sp.add_argument("--target-filename", default=None)

    sp = sub.add_parser("delete_file", help="Delete a file")
    sp.add_argument("--file-id", required=True)

    sp = sub.add_parser("mkdir", help="Create a directory")
    sp.add_argument("--name", required=True)
    sp.add_argument("--parent-path", default="/")

    sp = sub.add_parser("get_file_url", help="Get download URL for a file")
    sp.add_argument("--file-id", required=True)

    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    action = args.action
    base = "/blackboard/files"

    if action == "list_files":
        _output(api_call("GET", f"{base}?parent_path={args.path}"))

    elif action == "read_file":
        _output(api_call("GET", f"{base}/{args.file_id}/content"))

    elif action == "write_file":
        if args.file:
            import mimetypes
            import os
            fname = args.filename or os.path.basename(args.file)
            ct = args.content_type or mimetypes.guess_type(args.file)[0] or "application/octet-stream"
            _output(upload_file(args.file, f"{base}/upload-multipart", fname, args.parent_path, ct))
        else:
            fname = args.filename or "untitled"
            body = {
                "filename": fname,
                "content": args.content_b64,
                "parent_path": args.parent_path,
                "content_type": args.content_type or "application/octet-stream",
            }
            _output(api_call("POST", f"{base}/upload", body))

    elif action == "copy_file":
        body = {
            "target_parent_path": args.target_parent_path,
            "target_filename": args.target_filename,
        }
        _output(api_call("POST", f"{base}/{args.file_id}/copy", body))

    elif action == "delete_file":
        _output(api_call("DELETE", f"{base}/{args.file_id}"))

    elif action == "mkdir":
        body = {"name": args.name, "parent_path": args.parent_path}
        _output(api_call("POST", f"{base}/mkdir", body))

    elif action == "get_file_url":
        _output(api_call("GET", f"{base}/{args.file_id}/url"))


if __name__ == "__main__":
    main()
