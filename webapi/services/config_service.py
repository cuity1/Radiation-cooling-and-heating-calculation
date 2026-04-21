from __future__ import annotations

import configparser
import shutil
from datetime import datetime
from pathlib import Path

from ..settings import settings


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    return _project_root() / "default" / "config.ini"


def active_config_path() -> Path:
    # Legacy global config location (before per-user configs were introduced)
    return settings.data_dir / "config.ini"


def ensure_active_config_exists() -> Path:
    dst = active_config_path()
    if dst.exists():
        return dst

    src = default_config_path()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        raise FileNotFoundError(f"Default config not found: {src}")
    shutil.copyfile(src, dst)
    return dst


def user_config_path(user_id: int) -> Path:
    """
    Per-user editable config path.

    Example: data/user_configs/123.ini
    """
    return settings.data_dir / "user_configs" / f"{user_id}.ini"


def ensure_user_config_exists(user_id: int) -> Path:
    """
    Ensure per-user config exists by copying from the project default config.

    IMPORTANT:
    - Each user must have an isolated ini file (data/user_configs/{user_id}.ini).
    - Do NOT use the legacy global active config (data/config.ini) as the template,
      otherwise one user's edits can accidentally become the baseline for another user.
    """
    dst = user_config_path(user_id)
    if dst.exists():
        return dst

    base = default_config_path()

    dst.parent.mkdir(parents=True, exist_ok=True)
    if not base.exists():
        raise FileNotFoundError(f"Base config not found: {base}")
    shutil.copyfile(base, dst)
    return dst


def load_config_raw(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_config(path: Path) -> dict:
    cp = configparser.ConfigParser()
    cp.read(path, encoding="utf-8")

    out: dict[str, dict[str, str]] = {}
    for section in cp.sections():
        out[section] = {}
        for k, v in cp.items(section):
            out[section][k] = v
    return out


def _normalize_content(content: str) -> str:
    """
    Fix common encoding/input mistakes in INI content before saving.

    Replaces full-width Chinese comma (U+FF0C) and other common
    comma variants with standard ASCII comma (U+002C) across all
    key=value lines.
    """
    COMMA_VARIANTS = ['\uff0c', '\u3001', '\u002c']  # Chinese comma, ideographic comma, ASCII comma
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Only normalize active key=value lines (skip section headers, comments, blank lines)
        if '=' in stripped and not stripped.startswith((';', '#', '[')):
            key, _, raw_value = stripped.partition('=')
            value_part = raw_value.lstrip()
            # Replace all comma variants with standard comma
            for cv in COMMA_VARIANTS:
                if cv in value_part:
                    value_part = value_part.replace(cv, ',')
            lines[i] = f"{key} = {value_part}"
    return '\n'.join(lines)


def _validate_before_save(content: str) -> None:
    """
    Validate that config content is parseable by configparser.
    Raises ValueError with a descriptive message on failure.
    """
    cp = configparser.ConfigParser()
    cp.read_string(content)


def save_config(content: str) -> Path:
    # Normalize: fix Chinese commas, etc.
    content = _normalize_content(content)
    # Validate parse
    _validate_before_save(content)

    dst = ensure_active_config_exists()

    # backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = settings.data_dir / "config_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"config_{ts}.ini"
    shutil.copyfile(dst, backup_path)

    dst.write_text(content, encoding="utf-8")
    return dst


def save_user_config(content: str, user_id: int) -> Path:
    """
    Save per-user config content, with simple validation and backup.
    """
    # Normalize: fix Chinese commas, etc.
    content = _normalize_content(content)
    # Validate parse
    _validate_before_save(content)

    dst = ensure_user_config_exists(user_id)

    # backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = settings.data_dir / "config_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"config_{user_id}_{ts}.ini"
    shutil.copyfile(dst, backup_path)

    dst.write_text(content, encoding="utf-8")
    return dst


def restore_user_config(user_id: int) -> Path:
    """
    Restore a user's config by copying the admin reference file (1.ini) as a replacement.

    This effectively resets the user's parameters to the admin default, useful when
    a user's config file has become corrupted or contains bad values.
    """
    admin_src = user_config_path(1)
    dst = user_config_path(user_id)

    if admin_src == dst:
        # User 1 is the admin reference; nothing to restore.
        return dst

    if not admin_src.exists():
        raise FileNotFoundError(f"Admin reference config not found: {admin_src}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = settings.data_dir / "config_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"config_{user_id}_restore_{ts}.ini"
    if dst.exists():
        shutil.copyfile(dst, backup_path)

    shutil.copyfile(admin_src, dst)
    return dst
