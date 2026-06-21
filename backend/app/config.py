import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://aistock:aistock@localhost:5432/aistock",
)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "aistock123")
USE_SQLITE_FALLBACK = os.getenv("AISTOCK_SQLITE", "").lower() in ("1", "true", "yes")

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "aistock_evidence")
QDRANT_DOCUMENTS_COLLECTION = os.getenv("QDRANT_DOCUMENTS_COLLECTION", "aistock_documents")

LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_ENABLED = os.getenv("LLM_ENABLED", "auto").lower()  # auto | on | off

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "aistock")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "aistock123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "aistock-docs")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
USE_NEO4J_TRAVERSAL = os.getenv("USE_NEO4J_TRAVERSAL", "auto").lower()

# 数据接入适配器：mock | wind | cninfo
DATA_ADAPTER = os.getenv("DATA_ADAPTER", "mock")

# Wind 网关（live 模式需 WIND_API_KEY + WIND_API_URL）
WIND_API_KEY = os.getenv("WIND_API_KEY", "")
WIND_API_URL = os.getenv("WIND_API_URL", "http://localhost:8088/wind")
WIND_API_TIMEOUT = float(os.getenv("WIND_API_TIMEOUT", "30"))

# 巨潮网关（live 模式需 CNINFO_API_URL）
CNINFO_API_URL = os.getenv("CNINFO_API_URL", "")
CNINFO_API_TIMEOUT = float(os.getenv("CNINFO_API_TIMEOUT", "30"))

# 向量 embedding：auto 有 LLM_API_KEY 时用 API，否则伪向量
EMBEDDING_ENABLED = os.getenv("EMBEDDING_ENABLED", "auto").lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))
