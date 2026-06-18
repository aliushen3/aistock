# 设计文档索引

## 总方案（入口）

**请先阅读 → [DESIGN.md](./DESIGN.md)**

《产业瓶颈 Alpha 智能选股系统 — 总体方案设计》整合了：

- 原《产业瓶颈Alpha智能选股系统整体设计方案》（docx）
- `docs/` 目录下全部分册补充与修订

**冲突时以 `DESIGN.md` 为准。**

---

## 分册文档

| 文档 | 说明 |
|------|------|
| [DESIGN.md](./DESIGN.md) | **总方案设计文档（本文档集入口）** |
| [00-system-positioning.md](./00-system-positioning.md) | 系统定位、定性/量化边界 |
| [01-dual-logic-fusion.md](./01-dual-logic-fusion.md) | 双投研逻辑融合标准 |
| [02-knowledge-engineering.md](./02-knowledge-engineering.md) | 知识工程蓝图 |
| [03-human-in-loop.md](./03-human-in-loop.md) | 人机协同流程 |
| [04-graphrag-design.md](./04-graphrag-design.md) | GraphRAG 推理设计 |
| [05-serenity-algorithm.md](./05-serenity-algorithm.md) | Serenity 逆向溯源算法 |
| [06-hint-score-engine.md](./06-hint-score-engine.md) | 瓶颈提示分规则引擎 |
| [07-data-blueprint.md](./07-data-blueprint.md) | 数据蓝图 |
| [08-mvp-scope.md](./08-mvp-scope.md) | 一期 MVP 范围 |
| [09-evaluation.md](./09-evaluation.md) | 评估与验证 |
| [10-tech-stack.md](./10-tech-stack.md) | 技术栈选型 |
| [11-palantir-ontology.md](./11-palantir-ontology.md) | **Palantir Ontology 语义层实现** |

## 阅读建议

```
首次阅读：DESIGN.md（全文通读）
深入专题：按上表跳转对应分册
原方案对照：DESIGN.md 附录 §14.1 修订对照表
```

## 核心修订摘要

1. 定位：**知识驱动的定性投研辅助系统**
2. GNN 打分 → **规则提示分 + 人工确认**
3. 自动化选股 → **辅助式选股 + 人工入池**
4. 双图库 → **单 Neo4j**；Flink → **Celery**
5. 一期聚焦 **AI 算力** 单赛道 MVP
6. 知识表示采用 **Palantir Ontology 语义层**（自建，不依赖商业产品）
