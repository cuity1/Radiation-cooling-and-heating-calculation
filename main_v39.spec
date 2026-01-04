# -*- mode: python ; coding: utf-8 -*-

"""Stable PyInstaller spec.

Goals:
- Use main.py as the single authoritative entry point (avoid main_v39.py indirection).
- Fix module resolution by pinning pathex to the project root.
- Make console behavior explicit.

Usage:
    pyinstaller --clean --noconfirm main_v39.spec

Note:
- When PyInstaller executes the spec, __file__ might not be defined in some contexts.
  We therefore compute the project root from the current working directory.
"""

import os

# PyInstaller typically executes the spec with CWD set to the directory containing the spec.
# Using abspath('.') avoids relying on __file__.
PROJECT_ROOT = os.path.abspath('.')


a = Analysis(
    ['main.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[(os.path.join(PROJECT_ROOT, 'default'), 'default')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main_v39',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # console=True shows a console window; set False for GUI-only.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
