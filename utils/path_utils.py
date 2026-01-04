"""Path/resource helpers."""

from __future__ import annotations

import os
import sys


def res_path(*parts: str) -> str:
    """Resource path helper (dev env / PyInstaller onefile)."""
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = os.path.abspath('.')
    return os.path.join(base, *parts)


def external_default_dir() -> str:
    run_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath('.')
    return os.path.join(run_dir, 'default')
