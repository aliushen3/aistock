from __future__ import annotations

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL, USE_SQLITE_FALLBACK
from app.db.base import Base

logger = logging.getLogger(__name__)

_db_url = DATABASE_URL
if USE_SQLITE_FALLBACK:
    _db_url = "sqlite:///./aistock.db"

_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}
engine = create_engine(_db_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> bool:
    """建表并返回是否连接成功。"""
    from app.db import models  # noqa: F401

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        Base.metadata.create_all(bind=engine)
        return True
    except Exception as e:
        logger.warning("数据库初始化失败，将使用内存模式: %s", e)
        return False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
