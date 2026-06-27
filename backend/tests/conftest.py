import os

os.environ.setdefault("AISTOCK_SQLITE", "1")
os.environ.setdefault("LOAD_DEMO_SEED", "true")

from app.db import models  # noqa: F401,E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402

# 测试库为持久化 SQLite，按当前模型重建 schema，避免旧表缺列或状态跨运行泄漏。
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
