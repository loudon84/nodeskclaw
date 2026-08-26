from __future__ import annotations

from tools.release.subprocess_text import command_output, run_command


def test_command_output_prefers_stderr():
    class Result:
        stderr = " wheel build failed "
        stdout = "ignored"
        returncode = 1

    text = command_output(Result())
    assert "wheel build failed" in text
    assert "ignored" in text


def test_command_output_handles_none_streams():
    class Result:
        stderr = None
        stdout = None
        returncode = 1

    assert command_output(Result(), "fallback") == "fallback"
