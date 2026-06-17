# 技术栈选型

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend: React 18 + TypeScript + Vite + Ant Design + G6   │
├─────────────────────────────────────────────────────────────┤
│  API: FastAPI (Python 3.11+)                                │
├──────────────┬──────────────┬──────────────┬──────────────┤
│  业务服务     │  知识工程     │  推理服务     │  任务调度     │
│  services/   │  kg/         │  reasoning/  │  Celery      │
├──────────────┴──────────────┴──────────────┴──────────────┤
│  Neo4j │ PostgreSQL │ Qdrant │ Redis │ MinIO              │
└─────────────────────────────────────────────────────────────┘
```

## 2. 前端

| 类别 | 选型 | 版本 |
|------|------|------|
| 框架 | React | 18.x |
| 语言 | TypeScript | 5.x |
| 构建 | Vite | 5.x |
| UI | Ant Design | 5.x |
| 图谱 | AntV G6 | 4.x |
| 图表 | ECharts | 5.x |
| 状态 | TanStack Query + Zustand | latest |
| 路由 | React Router | 6.x |
| HTTP | Axios | 1.x |

## 3. 后端

| 类别 | 选型 | 版本 |
|------|------|------|
| 语言 | Python | 3.11+ |
| Web | FastAPI | 0.100+ |
| ORM | SQLAlchemy | 2.x |
| 迁移 | Alembic | 1.x |
| 任务 | Celery + Redis | 5.x / 7.x |
| 校验 | Pydantic | 2.x |

## 4. 数据与知识

| 类别 | 选型 | 用途 |
|------|------|------|
| 图数据库 | Neo4j | 产业链图谱 |
| 关系库 | PostgreSQL | 业务数据、溯源、审计 |
| 向量库 | Qdrant | 研报 RAG |
| 缓存 | Redis | 会话、队列、热点 |
| 对象存储 | MinIO | PDF、原始文档 |
| 本体 | OWLready2 + Protégé | OWL 约束 |

## 5. AI / 推理

| 类别 | 选型 | 说明 |
|------|------|------|
| LLM | DeepSeek API / GLM-4 API | 一期 API，不自托管 |
| 编排 | LangChain（可选） | GraphRAG Pipeline |
| 抽取 | Prompt + 本体约束 | 三元组抽取 |

## 6. 部署

| 类别 | 选型 |
|------|------|
| 容器 | Docker + Docker Compose |
| 代理 | Nginx |
| 日志 | structlog + 文件 |

## 7. 目录结构

```
aistock/
├── docs/                 # 设计文档
├── ontology/             # OWL 本体文件
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 路由
│   │   ├── models/       # SQLAlchemy 模型
│   │   ├── schemas/      # Pydantic
│   │   ├── services/     # 业务逻辑
│   │   │   ├── hint_score.py
│   │   │   ├── serenity_trace.py
│   │   │   └── graphrag.py
│   │   ├── kg/           # 图谱、Neo4j
│   │   └── tasks/        # Celery 任务
│   ├── config/
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/
│       ├── components/
│       │   ├── GraphCanvas/   # G6 图谱
│       │   └── ReportReview/
│       └── api/
├── docker-compose.yml
└── README.md
```

## 8. 原方案技术修订

| 原方案 | MVP 修订 |
|--------|---------|
| NebulaGraph + Neo4j | 仅 Neo4j |
| Flink | Celery Beat |
| Airflow | Celery Beat / APScheduler |
| Milvus | Qdrant（可换 Milvus） |
| GNN | 规则引擎 hint_score |
| LLM 微调 | API 调用 |
