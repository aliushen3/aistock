# AiStock Linux 部署指南

> 本文档描述在 Linux 服务器上部署 AiStock 的推荐方式：Docker Compose 拉起中间件，systemd 托管应用进程，Nginx 反代前后端。
> 设计背景见 [DESIGN.md](./DESIGN.md) §9；技术选型见 [10-tech-stack.md](./10-tech-stack.md)。

---

## 1. 架构概览

```text
                    ┌─────────────────────────────────────┐
  用户浏览器 ──────▶│ Nginx :80 / :443                     │
                    │  /        → frontend/dist (静态)     │
                    │  /api/    → FastAPI :8000            │
                    └──────────────────┬──────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
  PostgreSQL :5432              Neo4j :7687                   Qdrant :6333
  (Ontology + ODS)              (图投影/遍历)                  (向量检索)
         │                             │
         └──────── Redis :6379 ◀───────┘
                    │
              Celery Worker + Beat
                    │
              MinIO :9000 (研报对象存储)
```

---

## 2. 服务器要求

| 项目 | 建议 |
|------|------|
| OS | Ubuntu 22.04+ / Debian 12+ / 其他主流 Linux |
| CPU / 内存 | 4 核 / 8 GB 起（Neo4j + Qdrant 较吃内存） |
| 磁盘 | 50 GB+（日志、MinIO、数据库卷） |
| 网络 | 出网访问 LLM API（DeepSeek 等） |

### 2.1 需安装的软件

| 软件 | 用途 | 版本建议 |
|------|------|----------|
| Docker Engine | 运行中间件容器 | 24+ |
| Docker Compose Plugin | `docker compose` | v2 |
| Python | 后端运行时 | **3.11+** |
| Node.js | 前端构建 | **18+** |
| Nginx | 生产反代 | 1.18+ |

应用本身**不**需要单独安装 PostgreSQL / Neo4j 等——推荐全部用 `docker-compose.yml` 容器化。

### 2.2 中间件清单（docker compose）

仓库根目录 `docker-compose.yml` 定义 5 个服务：

| 服务 | 镜像 | 端口 | 必须性 |
|------|------|------|--------|
| postgres | postgres:15-alpine | 5432 | **生产必须** |
| neo4j | neo4j:5-community | 7474, 7687 | 强烈推荐 |
| redis | redis:7-alpine | 6379 | 异步任务 / Beat 必须 |
| qdrant | qdrant/qdrant:latest | 6333 | 研报向量检索推荐 |
| minio | minio/minio:latest | 9000, 9001 | 研报上传推荐 |

> **演示/单机调试**可设 `AISTOCK_SQLITE=1` 跳过 PostgreSQL（数据在本地 SQLite，不适合生产）。

---

## 3. 快速部署（开发 / 验证）

```bash
# 1. 克隆代码
git clone <repo-url> /opt/aistock
cd /opt/aistock

# 2. 中间件
docker compose up -d
docker compose ps

# 3. 后端
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../deploy/aistock.env.example ../deploy/aistock.env   # 按需编辑
set -a && source ../deploy/aistock.env && set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 前端（另开终端）
cd frontend
npm install
npm run dev    # http://<host>:5173，/api 代理到 8000
```

验收：

```bash
curl -s http://127.0.0.1:8000/api/v1/health | python3 -m json.tool
```

---

## 4. 生产部署

### 4.1 目录约定

```text
/opt/aistock/                 # 代码根目录
├── backend/.venv/
├── frontend/dist/            # npm run build 产出
├── deploy/
│   ├── aistock.env           # 环境变量（勿提交 Git）
│   ├── nginx/aistock.conf
│   └── systemd/*.service
└── docker-compose.yml
```

### 4.2 启动中间件

```bash
cd /opt/aistock
docker compose up -d

# 首次可查看日志
docker compose logs -f postgres neo4j
```

**生产务必修改** compose 中的默认密码（见 §7），或通过 `.env` 覆盖 `POSTGRES_PASSWORD`、`NEO4J_AUTH` 等。

### 4.3 配置环境变量

复制模板并编辑：

```bash
cp deploy/aistock.env.example deploy/aistock.env
chmod 600 deploy/aistock.env
vim deploy/aistock.env
```

完整变量说明见 [§5 环境变量](#5-环境变量)。

### 4.4 安装后端依赖

```bash
cd /opt/aistock/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

首次启动 API 时会自动：建表、灌种子数据、投影 Neo4j（见 `app/main.py` lifespan）。

### 4.5 构建前端

```bash
cd /opt/aistock/frontend
npm ci
npm run build
# 静态文件位于 frontend/dist/
```

### 4.6 Celery（异步抽取 + 定时任务）

Beat 调度包括：产业指标同步、MonitorWatch 扫描、观察清单刷新（见 `app/celery_app.py`）。

```bash
cd /opt/aistock/backend
source .venv/bin/activate
set -a && source /opt/aistock/deploy/aistock.env && set +a

# Worker
celery -A app.celery_app.celery_app worker -l info

# Beat（另开进程）
celery -A app.celery_app.celery_app beat -l info
```

无 Redis 时 API 对知识抽取等请求会**同步降级**，Beat 无法运行。

### 4.7 systemd（推荐）

```bash
sudo cp deploy/systemd/aistock-api.service /etc/systemd/system/
sudo cp deploy/systemd/aistock-celery-worker.service /etc/systemd/system/
sudo cp deploy/systemd/aistock-celery-beat.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable aistock-api aistock-celery-worker aistock-celery-beat
sudo systemctl start aistock-api aistock-celery-worker aistock-celery-beat
sudo systemctl status aistock-api
```

默认假设代码在 `/opt/aistock`、运行用户 `aistock`；路径不同请编辑 unit 文件。

### 4.8 Nginx

```bash
sudo cp deploy/nginx/aistock.conf /etc/nginx/sites-available/aistock
sudo ln -sf /etc/nginx/sites-available/aistock /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

HTTPS：在 `server` 块前增加 `listen 443 ssl` 与证书路径（Let's Encrypt / 内网 CA）。

---

## 5. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `postgresql://aistock:aistock@localhost:5432/aistock` | PostgreSQL 连接串 |
| `AISTOCK_SQLITE` | 空 | 设为 `1`/`true` 时用 SQLite（仅演示） |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt 地址 |
| `NEO4J_USER` | `neo4j` | Neo4j 用户名 |
| `NEO4J_PASSWORD` | `aistock123` | Neo4j 密码 |
| `USE_NEO4J_TRAVERSAL` | `auto` | `auto`/`on`/`off` 图遍历后端 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis |
| `CELERY_BROKER_URL` | 同 REDIS | Celery Broker |
| `CELERY_RESULT_BACKEND` | 同 REDIS | Celery 结果后端 |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant HTTP |
| `QDRANT_COLLECTION` | `aistock_evidence` | 证据向量集合 |
| `QDRANT_DOCUMENTS_COLLECTION` | `aistock_documents` | 文档分块集合 |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO 地址（无 `http://`） |
| `MINIO_ACCESS_KEY` | `aistock` | MinIO Access Key |
| `MINIO_SECRET_KEY` | `aistock123` | MinIO Secret Key |
| `MINIO_BUCKET` | `aistock-docs` | 存储桶名 |
| `LLM_API_KEY` | 空 | LLM Key（也可用 `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`） |
| `LLM_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容 API 基址 |
| `LLM_MODEL` | `deepseek-chat` | 模型名 |
| `LLM_ENABLED` | `auto` | `auto`/`on`/`off` |
| `EMBEDDING_ENABLED` | `auto` | 向量 embedding 策略 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding 模型 |
| `EMBEDDING_DIM` | `1536` | 向量维度 |
| `DATA_ADAPTER` | `mock` | 数据适配器 `mock`/`wind`/`cninfo` |
| `WIND_API_KEY` | 空 | Wind 网关 Key |
| `WIND_API_URL` | `http://localhost:8088/wind` | Wind 网关 URL |
| `CNINFO_API_URL` | 空 | 巨潮网关 URL |

模板文件：`deploy/aistock.env.example`。

---

## 6. 端口与防火墙

| 端口 | 服务 | 是否对公网开放 |
|------|------|----------------|
| 80 / 443 | Nginx | **是**（用户入口） |
| 8000 | FastAPI | 否（仅本机 / 内网） |
| 5432 | PostgreSQL | **否** |
| 6379 | Redis | **否** |
| 7687 / 7474 | Neo4j | **否** |
| 6333 | Qdrant | **否** |
| 9000 / 9001 | MinIO | **否**（管理台 9001 仅内网） |

```bash
# ufw 示例：仅开放 Web
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

Docker 默认将中间件端口绑定到 `0.0.0.0`。生产可在 `docker-compose.yml` 中改为 `127.0.0.1:5432:5432` 等，仅本机访问。

---

## 7. 安全与生产密钥

1. **勿使用** compose 默认密码（`aistock` / `aistock123`）上线。
2. `deploy/aistock.env` 权限设为 `600`，不提交 Git（已在 `.gitignore` 建议忽略 `deploy/aistock.env`）。
3. LLM / Wind / 巨潮等 API Key 仅通过环境变量注入。
4. MinIO 控制台（9001）不对公网暴露。
5. 高影响 Ontology Action（入池、发报告）在生产环境启用双人复核（见 [03-human-in-loop.md](./03-human-in-loop.md)）。

---

## 8. 健康检查与降级

```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

`components` 字段含义：

| 字段 | `false` 时行为 |
|------|----------------|
| `postgresql` | 回退内存种子 / SQLite（若启用） |
| `neo4j` | 内存图遍历，无 G6 多跳加速 |
| `qdrant` | 伪向量 / 关键词检索降级 |
| `minio` | 研报无法对象存储归档 |
| `llm` | Agent / GraphRAG 走规则 Pipeline |

---

## 9. 常见问题

**Q: API 启动报数据库连接失败？**  
确认 `docker compose ps` 中 postgres 为 healthy，且 `DATABASE_URL` 主机/密码与 compose 一致。

**Q: 前端页面空白或 API 404？**  
生产需 Nginx 同时托管 `dist/` 并将 `/api` 反代到 8000；勿直接暴露 Vite dev server。

**Q: 上传研报失败？**  
检查 `minio` 组件为 true；首次使用 MinIO 会自动创建 bucket。

**Q: Celery 任务一直 queued？**  
确认 Redis 可达且 `aistock-celery-worker` 在运行。

**Q: Neo4j 连接超时？**  
Neo4j 首次启动较慢，等待 30–60 秒后重启 API。

---

## 10. 相关文档

| 文档 | 内容 |
|------|------|
| [README.md](../README.md) | 项目简介与最短启动 |
| [DESIGN.md](./DESIGN.md) §13.3 | 快速启动命令 |
| [10-tech-stack.md](./10-tech-stack.md) | 技术栈与目录结构 |
| [07-data-blueprint.md](./07-data-blueprint.md) | 数据源与 ODS |
| [08-implementation-phases.md](./08-implementation-phases.md) | 建设阶段 |

---

## 11. 升级与备份

```bash
cd /opt/aistock
git pull
cd backend && source .venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm ci && npm run build
sudo systemctl restart aistock-api aistock-celery-worker
```

备份建议：

- PostgreSQL：`docker compose exec postgres pg_dump -U aistock aistock > backup.sql`
- Neo4j / Qdrant / MinIO：备份对应 Docker volume
- `ontology/registry/` 与 `backend/config/`：随 Git 版本管理
