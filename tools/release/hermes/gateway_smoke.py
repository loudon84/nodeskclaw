"""Gateway functional smoke for final Windows runtime (FR-214-22)."""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from tools.release.hermes.managed_config import render_managed_defaults_yaml

HttpGetter = Callable[[str, dict[str, str] | None, float], tuple[int, str]]


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_tcp(host: str, port: int, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.2)
    raise ValueError(f"gateway TCP not listening: {host}:{port}")


def _default_http_get(url: str, headers: dict[str, str] | None, timeout_s: float) -> tuple[int, str]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - localhost only
            body = response.read().decode("utf-8", errors="replace")
            return int(response.status), body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return int(exc.code), body


def _terminate_process(proc: subprocess.Popen[Any], *, grace_s: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=grace_s)
        return
    except subprocess.TimeoutExpired:
        pass
    proc.kill()
    try:
        proc.wait(timeout=3.0)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("gateway orphan process after force kill") from exc


def _tail_text(path: Path, *, limit: int = 4000) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= limit:
        return text
    return text[-limit:]


def _runtime_process_path(runtime_tree: Path) -> str:
    """Process-local PATH: bin;scripts;node;python;<inherited> (FR-215-06)."""
    managed = [
        str(runtime_tree / "bin"),
        str(runtime_tree / "scripts"),
        str(runtime_tree / "node"),
        str(runtime_tree / "python"),
    ]
    inherited = str(os.environ.get("PATH") or "")
    if not inherited:
        return os.pathsep.join(managed)
    return os.pathsep.join(managed + [inherited])


def run_gateway_smoke(
    runtime_tree: Path,
    *,
    profile: dict[str, Any],
    profile_name: str = "smc-managed",
    bind: str = "127.0.0.1",
    port: int | None = None,
    startup_timeout_s: float = 45.0,
    http_timeout_s: float = 10.0,
    http_get: HttpGetter | None = None,
    skip_if_not_windows: bool = True,
) -> dict[str, Any]:
    if skip_if_not_windows and os.name != "nt":
        return {"skipped": True, "reason": "non-windows"}

    hermes_exe = runtime_tree / "bin" / "hermes.exe"
    if not hermes_exe.is_file():
        raise ValueError("gateway smoke: hermes.exe missing")

    port = port or _pick_free_port()
    getter = http_get or _default_http_get
    work = runtime_tree.parent / f"gateway-smoke-{os.getpid()}-{port}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    api_key = secrets.token_urlsafe(32)
    env_path = work / ".env"
    config_path = work / "config.yaml"
    stdout_log = work / "gateway.stdout.log"
    stderr_log = work / "gateway.stderr.log"
    try:
        (work / "workspace").mkdir(parents=True, exist_ok=True)
        (work / "tmp").mkdir(parents=True, exist_ok=True)
        env_path.write_text(
            "\n".join(
                [
                    "API_SERVER_ENABLED=true",
                    f"API_SERVER_HOST={bind}",
                    f"API_SERVER_PORT={port}",
                    f"API_SERVER_KEY={api_key}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        # Minimal instance config for smoke; managed defaults compiled separately.
        managed_text = render_managed_defaults_yaml(profile, profile_name=profile_name)
        (work / "managed.defaults.yaml").write_text(managed_text, encoding="utf-8")
        config_path.write_text(
            "\n".join(
                [
                    "terminal:",
                    f'  cwd: "{str(work / "workspace").replace(chr(92), chr(92)+chr(92))}"',
                    "logging:",
                    "  level: INFO",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["HERMES_HOME"] = str(work)
        env["HERMES_AGENT_ROOT"] = str(runtime_tree / "node" / "hermes-agent")
        env["HERMES_NODE_ROOT"] = str(runtime_tree / "node")
        env["TEMP"] = str(work / "tmp")
        env["TMP"] = str(work / "tmp")
        env["PATH"] = _runtime_process_path(runtime_tree)
        env["API_SERVER_ENABLED"] = "true"
        env["API_SERVER_HOST"] = bind
        env["API_SERVER_PORT"] = str(port)
        env["API_SERVER_KEY"] = api_key
        # Do not leak key into parent process env permanently.
        env.pop("SMC_GATEWAY_SMOKE_KEY", None)

        # Never use PIPE here: hermes logs can fill the buffer and deadlock before TCP bind.
        with stdout_log.open("w", encoding="utf-8", errors="replace") as out_fh, stderr_log.open(
            "w", encoding="utf-8", errors="replace"
        ) as err_fh:
            proc = subprocess.Popen(
                [str(hermes_exe), "gateway", "run"],
                cwd=str(work / "workspace"),
                env=env,
                stdout=out_fh,
                stderr=err_fh,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            try:
                if proc.poll() is not None:
                    raise ValueError(
                        "gateway exited early: "
                        f"exit={proc.returncode}; "
                        f"stdout={_tail_text(stdout_log)}; "
                        f"stderr={_tail_text(stderr_log)}"
                    )
                try:
                    _wait_tcp(bind, port, startup_timeout_s)
                except ValueError as exc:
                    raise ValueError(
                        f"{exc}; "
                        f"exit={proc.poll()}; "
                        f"stdout={_tail_text(stdout_log)}; "
                        f"stderr={_tail_text(stderr_log)}"
                    ) from exc
                health_url = f"http://{bind}:{port}/health"
                models_url = f"http://{bind}:{port}/v1/models"
                status, _ = getter(health_url, None, http_timeout_s)
                if status != 200:
                    raise ValueError(
                        f"gateway /health failed: HTTP {status}; "
                        f"stderr={_tail_text(stderr_log)}"
                    )
                status, _ = getter(
                    models_url,
                    {"Authorization": f"Bearer {api_key}"},
                    http_timeout_s,
                )
                if status in {401, 403}:
                    raise ValueError(f"gateway /v1/models auth failed: HTTP {status}")
                if status != 200:
                    raise ValueError(
                        f"gateway /v1/models failed: HTTP {status}; "
                        f"stderr={_tail_text(stderr_log)}"
                    )
            finally:
                _terminate_process(proc)
                if proc.poll() is None:
                    raise ValueError("gateway orphan process remaining")
    finally:
        # Wipe secrets from temp tree.
        if env_path.is_file():
            env_path.write_text("", encoding="utf-8")
        shutil.rmtree(work, ignore_errors=True)

    return {"skipped": False, "bind": bind, "port": port, "ok": True}
