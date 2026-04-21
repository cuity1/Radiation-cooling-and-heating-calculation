from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "rccalc-webapi"
    api_prefix: str = "/api"

    # Scheduled cleanup: remove jobs older than N days except user 'All'
    cleanup_enabled: bool = True
    cleanup_days: int = 180
    cleanup_cron_hour: int = 6
    cleanup_cron_minute: int = 0
    cleanup_timezone: str = "Asia/Shanghai"

    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # IMPORTANT:
    # Use an absolute path anchored at the workspace root, not a CWD-relative "data/".
    # Otherwise, running uvicorn from a different working directory will silently read/write
    # a different data folder and user config changes won't take effect.
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    uploads_dir: Path = data_dir / "uploads"
    jobs_dir: Path = data_dir / "jobs"

    # Folder to store user-uploaded atmospheric DLL presets.
    # Each file is renamed to "<stem>_<user_id>.dll" to avoid conflicts across users.
    atm_uploads_dir: Path = uploads_dir / "atm_presets"

    redis_url: str = "redis://localhost:6379/0"
    rq_queue_name: str = "default"

    # Proxy settings for GEE (Google Earth Engine) API access from China.
    # Format: "http://host:port" or "socks5://host:port".
    # Leave empty string "" to use no proxy (direct connection).
    gee_proxy: str = ""

    # Windows-friendly default: execute jobs synchronously in the API process.
    # When running on Linux/Docker/WSL, you can set this to True and use rq worker.
    rq_is_async: bool = False

    sqlite_path: Path = data_dir / "rccalc.db"

    # AI 问答配置（OpenAI 兼容接口）
    # ai_base_url: str = "https://ai.td.ee"
    # ai_model: str = "gpt-5.4"
    # ai_api_key: str = "sk-43cbbd100f2e087111715385ecb5d712a50c609e6da012161c5ae8ba3ca5c90c"
    ai_base_url: str = "https://www.xdaicn.top"
    ai_model: str = "gpt-5.4"
    ai_api_key: str = "sk-DDmVH8QpKnQ3SQ6m164FIZJf5wgYFdwtdpAE4Pi8ARFoNEfB"

settings = Settings()
