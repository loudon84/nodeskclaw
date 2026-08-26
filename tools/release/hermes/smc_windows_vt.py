"""Enable Windows VT so embed CPython can render Hermes ANSI (setup wizard).

python312._pth forces isolated mode, which skips sitecustomize. This module is
imported from a site-packages .pth so it still runs at interpreter startup.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

try:
    from colorama import just_fix_windows_console
except Exception:
    just_fix_windows_console = None

ENABLE_PROCESSED_OUTPUT = 0x0001
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE = -12


def enable_windows_vt() -> None:
    if sys.platform != "win32":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel32.GetStdHandle.restype = wintypes.HANDLE
        kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetConsoleMode.restype = wintypes.BOOL
        kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.SetConsoleMode.restype = wintypes.BOOL
        invalid = ctypes.c_void_p(-1).value
        for std_id in (STD_OUTPUT_HANDLE, STD_ERROR_HANDLE):
            handle = kernel32.GetStdHandle(std_id)
            handle_value = ctypes.cast(handle, ctypes.c_void_p).value
            if not handle_value or handle_value == invalid:
                continue
            mode = wintypes.DWORD()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                continue
            new_mode = mode.value | ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            if new_mode != mode.value:
                kernel32.SetConsoleMode(handle, new_mode)
    except Exception:
        pass
    if just_fix_windows_console is None:
        return
    try:
        just_fix_windows_console()
    except Exception:
        pass


if __name__ == "smc_windows_vt":
    enable_windows_vt()
