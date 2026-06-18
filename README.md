# 产业瓶颈 Alpha 智能选股系统（AiStock）

**知识驱动的定性投研辅助系统** — 融合买方产业图谱与 Serenity 逆向选股逻辑。

> 量化打分仅作辅助排序与提示，不构成自动投资决策。所有入池与报告发布须经人工确认。

## 文档索引

| 文档 | 说明 |
|------|------|
| **[DESIGN.md](docs/DESIGN.md)** | **总体方案设计文档（主文档，优先阅读）** |
| [00-system-positioning](docs/00-system-positioning.md) | 系统定位、定性/量化边界 |
| [01-dual-logic-fusion](docs/01-dual-logic-fusion.md) | 双投研逻辑融合标准 |
| [02-knowledge-engineering](docs/02-knowledge-engineering.md) | 知识工程蓝图 |
| [03-human-in-loop](docs/03-human-in-loop.md) | 人机协同流程 |
| [04-graphrag-design](docs/04-graphrag-design.md) | GraphRAG 推理设计 |
| [05-serenity-algorithm](docs/05-serenity-algorithm.md) | Serenity 逆向溯源算法 |
| [06-hint-score-engine](docs/06-hint-score-engine.md) | 瓶颈提示分规则引擎 |
| [07-data-blueprint](docs/07-data-blueprint.md) | 数据蓝图 |
| [08-mvp-scope](docs/08-mvp-scope.md) | 一期 MVP 范围 |
| [09-evaluation](docs/09-evaluation.md) | 评估与验证 |
| [10-tech-stack](docs/10-tech-stack.md) | 技术栈选型 |
| [11-palantir-ontology](docs/11-palantir-ontology.md) | Palantir Ontology 语义层 |

## 技术栈

- **前端**：React 18 + TypeScript + Vite + Ant Design + G6
- **后端**：Python 3.11 + FastAPI + Celery
- **知识**：Neo4j + PostgreSQL + Qdrant + OWL
- **AI**：DeepSeek / GLM-4 API + GraphRAG

## 快速启动

```bash
# 启动基础设施
docker compose up -d

# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

## 一期 MVP

聚焦 **AI 算力** 单赛道，跑通：图谱 → 双逻辑候选 → GraphRAG 报告 → 人工入池。

## 免责声明

本系统为智能投研辅助工具，输出内容不构成投资建议，需专业研究员二次复核。
