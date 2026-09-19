"""Start Knowledge API on 4530 and the ingestion worker together."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NO_PROXY = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,localhost,127.0.0.1"


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["no_proxy"] = NO_PROXY
    env["NO_PROXY"] = NO_PROXY
    return env


def _uv() -> str:
    found = shutil.which("uv")
    if not found:
        print("uv not found in PATH", file=sys.stderr)
        sys.exit(1)
    return found


def _popen(args: list[str]) -> subprocess.Popen[str]:
    kwargs: dict = {
        "cwd": ROOT,
        "env": _child_env(),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(args, **kwargs)


def _pump(prefix: str, proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(f"{prefix} {line}")
        sys.stdout.flush()


def _stop(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def main() -> None:
    uv = _uv()
    host = os.environ.get("HOST", "0.0.0.0")
    port = os.environ.get("PORT", "4530")
    api = _popen(
        [
            uv,
            "run",
            "uvicorn",
            "app.main:app",
            "--host",
            host,
            "--port",
            port,
            "--reload",
            "--log-level",
            "info",
        ]
    )
    worker = _popen([uv, "run", "python", "-m", "app.workers.ingestion_worker"])
    print(f"api http://127.0.0.1:{port} pid={api.pid}")
    print(f"ingestion worker pid={worker.pid}")
    print("Ctrl+C to stop both")

    threads = [
        threading.Thread(target=_pump, args=("[api]", api), daemon=True),
        threading.Thread(target=_pump, args=("[ingestion]", worker), daemon=True),
    ]
    for thread in threads:
        thread.start()

    try:
        while True:
            if api.poll() is not None:
                print(f"api exited code={api.returncode}", file=sys.stderr)
                break
            if worker.poll() is not None:
                print(f"ingestion worker exited code={worker.returncode}", file=sys.stderr)
                break
            threads[0].join(timeout=0.5)
    except KeyboardInterrupt:
        print("stopping")
    finally:
        _stop(api)
        _stop(worker)


if __name__ == "__main__":
    main()
