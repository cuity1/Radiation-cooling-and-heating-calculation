from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..settings import settings


def _db_url() -> str:
    # sqlite:///relative/path.db
    return f"sqlite:///{settings.sqlite_path.as_posix()}"


engine = create_engine(
    _db_url(),
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
