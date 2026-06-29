import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://aistock:aistock@localhost:5432/aistock",
)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "aistock123")
USE_SQLITE_FALLBACK = os.getenv("AISTOCK_SQLITE", "").lower() in ("1", "true", "yes")

# 演示种子：false=生产空图启动；true=首次建库灌入 seed_ai_compute.json（仅 demo）
LOAD_DEMO_SEED = os.getenv("LOAD_DEMO_SEED", "false").lower() in ("1", "true", "yes")

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

# 数据接入适配器（按类型拆分）
# market: mock | akshare | tushare | auto（auto: tushare 主 → akshare 备）
DATA_ADAPTER = os.getenv("DATA_ADAPTER", "mock")
# market: mock | akshare | tushare | tencent | auto（auto: tushare → tencent → akshare）
DATA_ADAPTER_MARKET = os.getenv("DATA_ADAPTER_MARKET", "mock")
DATA_ADAPTER_ANNOUNCEMENT = os.getenv("DATA_ADAPTER_ANNOUNCEMENT", "mock")
DATA_ADAPTER_METRICS = os.getenv("DATA_ADAPTER_METRICS", "mock")
# financial: mock | tushare | sina（新浪财报三表直连）
DATA_ADAPTER_FINANCIAL = os.getenv("DATA_ADAPTER_FINANCIAL", "mock")
# research: mock | em | eastmoney（东财 reportapi 直连）
DATA_ADAPTER_RESEARCH = os.getenv("DATA_ADAPTER_RESEARCH", "mock")
# constituent: mock | akshare（板块/概念成分股 → OntCompany 真实代码）
DATA_ADAPTER_CONSTITUENT = os.getenv("DATA_ADAPTER_CONSTITUENT", "mock")

# 公告/研报回看天数
ANNOUNCEMENT_LOOKBACK_DAYS = int(os.getenv("ANNOUNCEMENT_LOOKBACK_DAYS", "90"))
RESEARCH_LOOKBACK_DAYS = int(os.getenv("RESEARCH_LOOKBACK_DAYS", "90"))

# 巨潮网关（live 模式需 CNINFO_API_URL）
CNINFO_API_URL = os.getenv("CNINFO_API_URL", "")
CNINFO_API_TIMEOUT = float(os.getenv("CNINFO_API_TIMEOUT", "30"))

# AkShare / Tushare 行情
AKSHARE_RATE_LIMIT_SEC = float(os.getenv("AKSHARE_RATE_LIMIT_SEC", "0.5"))
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
TUSHARE_RATE_LIMIT_SEC = float(os.getenv("TUSHARE_RATE_LIMIT_SEC", "0.3"))

# 行情抓取网络（免费源不稳定时的兜底）
MARKET_FORCE_IPV4 = os.getenv("MARKET_FORCE_IPV4", "true").lower() in ("1", "true", "yes")
MARKET_HTTP_MAX_RETRY = int(os.getenv("MARKET_HTTP_MAX_RETRY", "3"))
MARKET_HTTP_RETRY_BACKOFF_SEC = float(os.getenv("MARKET_HTTP_RETRY_BACKOFF_SEC", "1.0"))

# 向量 embedding：auto 有 LLM_API_KEY 时用 API，否则伪向量
EMBEDDING_ENABLED = os.getenv("EMBEDDING_ENABLED", "auto").lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))
