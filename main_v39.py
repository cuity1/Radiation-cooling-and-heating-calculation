"""Backward-compatible entry point.

This file used to contain all logic. It now delegates to main.py.

Keeping this file allows existing PyInstaller commands like:
    pyinstaller -F --add-data "default;default" .\main_v39.py
"""

from __future__ import annotations

from main import main


if __name__ == '__main__':
    main()
