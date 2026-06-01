import shlex

import pytest

from app.core.exceptions import AppException
from app.services.nfs_mount import PodFS


class FakeK8s:
    def __init__(self):
        self.commands = []

    async def exec_in_pod(self, ns, pod, command, container=None):
        self.commands.append({
            "ns": ns,
            "pod": pod,
            "command": command,
            "container": container,
        })
        return ""


@pytest.mark.asyncio
async def test_podfs_write_text_shell_quotes_single_quote_path() -> None:
    k8s = FakeK8s()
    fs = PodFS(k8s, "ns", "pod", "container")
    rel_path = ".openclaw/agent-bundles/q/skills/echo/bad'name.txt"

    await fs.write_text(rel_path, "payload")

    shell_command = k8s.commands[0]["command"][2]
    target = shlex.quote(f"/root/{rel_path}")
    assert k8s.commands[0]["command"][:2] == ["bash", "-c"]
    assert f"dirname {target}" in shell_command
    assert shell_command.endswith(f"> {target}")
    assert f"'/root/{rel_path}'" not in shell_command


@pytest.mark.asyncio
async def test_podfs_rejects_paths_outside_root_before_exec() -> None:
    k8s = FakeK8s()
    fs = PodFS(k8s, "ns", "pod", "container")

    with pytest.raises(AppException) as exc:
        await fs.write_text("../../etc/passwd", "payload")

    assert exc.value.message_key == "errors.enterprise_files.invalid_path"
    assert k8s.commands == []


@pytest.mark.asyncio
async def test_podfs_rejects_control_chars_before_exec() -> None:
    k8s = FakeK8s()
    fs = PodFS(k8s, "ns", "pod", "container")

    with pytest.raises(AppException) as exc:
        await fs.write_text(".openclaw/a\0b.txt", "payload")

    assert exc.value.message_key == "errors.enterprise_files.invalid_path"
    assert k8s.commands == []
