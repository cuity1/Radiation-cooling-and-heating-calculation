from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pathlib import Path

from ..settings import settings
from .file_processing_service import combine_reflectance_and_transmittance


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ActiveInput:
    id: str
    path: str
    original_name: str
    updated_at: str


def _active_inputs_path() -> Path:
    # Legacy global path (user_id = 0). Kept for backward-compat helper APIs.
    return settings.data_dir / "active_inputs" / "0.json"


def _active_inputs_path_for_user(user_id: int) -> Path:
    """Return per-user path for active inputs metadata.

    Each user gets an isolated JSON file:
    data/active_inputs/{user_id}.json
    """
    return settings.data_dir / "active_inputs" / f"{user_id}.json"


class _FileLock:
    """Cross-platform advisory file lock (best-effort).

    Prevent concurrent writers from clobbering active_inputs.json (lost updates).
    """

    def __init__(self, path: Path):
        # Use a dedicated .lock file so that we never lock the data file itself.
        # This avoids Windows "Permission denied" errors when replacing the JSON.
        self.path = path.with_suffix(path.suffix + ".lock")
        self._fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure file exists so locking works reliably.
        self._fh = open(self.path, "a+", encoding="utf-8")
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fh.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        except Exception:
            # Best-effort: if lock isn't available, continue.
            pass
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._fh:
                try:
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                self._fh.close()
        finally:
            self._fh = None
        return False


def _atomic_write_text(path: Path, text: str) -> None:
    """Atomic write (write temp then replace).

    Windows note:
    `Path.replace()` maps to `os.replace()`, which can raise WinError 5
    (Access is denied) if the destination is momentarily locked (e.g. by
    antivirus, sync clients like BaiduSyncdisk/OneDrive, or another process).

    We mitigate by:
    - writing to a uniquely named temp file in the same directory
    - fsync to reduce timing windows
    - retrying replace a few times
    - falling back to a non-atomic write as a last resort (better than 500)
    """

    import time
    import uuid

    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            try:
                f.flush()
                os.fsync(f.fileno())
            except Exception:
                # Best-effort; some filesystems may not support fsync.
                pass

        last_exc: Exception | None = None
        for attempt in range(8):
            try:
                tmp.replace(path)
                return
            except PermissionError as e:
                last_exc = e
                # Small backoff to let Windows release locks.
                time.sleep(0.05 * (attempt + 1))

        # Fallback: non-atomic overwrite (still under our lock file).
        # This prevents uploads from failing if replace is consistently blocked.
        path.write_text(text, encoding="utf-8")

        if last_exc is not None and os.name != "nt":
            # Non-Windows should not normally hit PermissionError.
            raise last_exc
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def load_active_inputs_raw_for_user(user_id: int) -> dict[str, Any]:
    """Load raw metadata for a single user from that user's JSON file."""
    p = _active_inputs_path_for_user(user_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_active_inputs_raw_for_user(user_id: int, data: dict[str, Any]) -> None:
    """Persist raw metadata for a single user to that user's JSON file."""
    p = _active_inputs_path_for_user(user_id)
    # Lock + atomic write to avoid concurrent writers clobbering the JSON file,
    # while remaining safe on Windows.
    with _FileLock(p):
        _atomic_write_text(p, json.dumps(data, ensure_ascii=False, indent=2))


def get_active_input_for_user(user_id: int, kind: str) -> ActiveInput | None:
    raw = load_active_inputs_raw_for_user(user_id)
    node = raw.get(kind)
    if not isinstance(node, dict):
        return None
    active_id = node.get("active_id")
    path = node.get("path")
    original_name = node.get("original_name")
    updated_at = node.get("updated_at")
    if not (isinstance(active_id, str) and isinstance(path, str) and isinstance(original_name, str)):
        return None
    if not isinstance(updated_at, str):
        updated_at = ""
    return ActiveInput(id=active_id, path=path, original_name=original_name, updated_at=updated_at)


def set_active_input_for_user(
    user_id: int, *, kind: str, active_id: str, path: str, original_name: str
) -> None:
    raw = load_active_inputs_raw_for_user(user_id)
    raw[kind] = {
        "active_id": active_id,
        "path": path,
        "original_name": original_name,
        "updated_at": _now_iso(),
    }
    save_active_inputs_raw_for_user(user_id, raw)


def clear_active_input_for_user(user_id: int, kind: str) -> None:
    """Remove a single active input of the given kind for a given user."""
    raw = load_active_inputs_raw_for_user(user_id)
    if kind in raw:
        del raw[kind]
        save_active_inputs_raw_for_user(user_id, raw)


def delete_active_inputs_for_user(user_id: int) -> None:
    """Remove all active input records for a given user (best-effort)."""
    p = _active_inputs_path_for_user(user_id)
    try:
        p.unlink()
    except FileNotFoundError:
        return
    except Exception:
        # Best-effort; ignore errors (e.g. permission issues).
        return


def has_active_reflectance_and_emissivity_for_user(user_id: int) -> bool:
    return (
        get_active_input_for_user(user_id, "reflectance") is not None
        and get_active_input_for_user(user_id, "emissivity") is not None
    )


def active_ready_for_user(user_id: int) -> bool:
    r = get_active_input_for_user(user_id, "reflectance")
    e = get_active_input_for_user(user_id, "emissivity")
    if not (r and e):
        return False
    return Path(r.path).exists() and Path(e.path).exists()


def get_combined_reflectance_path_for_user(user_id: int) -> str | None:
    """Return path to effective reflectance spectrum used for calculations.

    Logic:
    - If no active reflectance, return None (caller must handle readiness checks).
    - If there is no active transmittance for this user, return reflectance path as-is.
    - If both reflectance and transmittance exist, generate (or reuse) a combined R+T file
      on the reflectance wavelength grid, but do NOT expose it via /uploads APIs.
    """
    r = get_active_input_for_user(user_id, "reflectance")
    if not r:
        return None

    t = get_active_input_for_user(user_id, "transmittance")
    # No transmittance uploaded: fall back to pure reflectance.
    if not t:
        return r.path

    r_path = Path(r.path)
    t_path = Path(t.path)
    if not (r_path.exists() and t_path.exists()):
        # Fallback to reflectance if transmittance file is missing.
        return r.path if r_path.exists() else None

    # Deterministic file name per (reflectance_id, transmittance_id) pair
    combined_dir = settings.uploads_dir / "processed" / "reflect_plus_transmittance"
    combined_name = f"{r.id}__{t.id}.txt"
    combined_path = combined_dir / combined_name

    if combined_path.exists():
        return str(combined_path)

    out_path = combine_reflectance_and_transmittance(r_path, t_path, combined_dir, combined_name=combined_name)
    return str(out_path)


# Backwards-compatible helpers (used by worker or legacy code if any).
# They operate on a special "global" bucket with user_id = 0.

def get_active_input(kind: str) -> ActiveInput | None:
    return get_active_input_for_user(0, kind)


def set_active_input(*, kind: str, active_id: str, path: str, original_name: str) -> None:
    set_active_input_for_user(0, kind=kind, active_id=active_id, path=path, original_name=original_name)


def has_active_reflectance_and_emissivity() -> bool:
    return has_active_reflectance_and_emissivity_for_user(0)


def active_ready() -> bool:
    return active_ready_for_user(0)
