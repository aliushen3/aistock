import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://aistock:aistock@localhost:5432/aistock",
)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "aistock123")
USE_SQLITE_FALLBACK = os.getenv("AISTOCK_SQLITE", "").lower() in ("1", "true", "yes")
