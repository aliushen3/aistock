# 设计文档索引

## 总方案（入口）

**请先阅读 → [DESIGN.md](./DESIGN.md)**（v3.0 AI Native 投研操作系统）

《产业瓶颈 Alpha 智能选股系统 — 总体方案设计》整合了原 docx 与全部分册。**冲突时以 `DESIGN.md` 为准。**

> **v3.0 三条贯穿主线**：**反证优先**（独立 BearCaseAgent + 入池硬闸门）、**知识保鲜**（保鲜状态机 + 瓶颈生命周期）、**预期差与价值捕获**（入池三道闸）。见 DESIGN.md §1.4、§2.6、§5.7、§6.3、§6.4。

---

## 分册文档

| 文档 | 说明 |
|------|------|
| [DESIGN.md](./DESIGN.md) | **总方案（§3 架构与智能体体系）** |
| [00-system-positioning.md](./00-system-positioning.md) | 系统定位、AI Native 七层 |
| [01-dual-logic-fusion.md](./01-dual-logic-fusion.md) | 双投研逻辑融合 |
| [02-knowledge-engineering.md](./02-knowledge-engineering.md) | 知识工程蓝图 |
| [03-human-in-loop.md](./03-human-in-loop.md) | 人机协同 + Agent 提案 |
| [04-graphrag-design.md](./04-graphrag-design.md) | GraphRAG 推理 |
| [05-serenity-algorithm.md](./05-serenity-algorithm.md) | Serenity 逆向溯源 |
| [06-hint-score-engine.md](./06-hint-score-engine.md) | 瓶颈提示分 |
| [07-data-blueprint.md](./07-data-blueprint.md) | 数据蓝图 + ODS |
| [08-implementation-phases.md](./08-implementation-phases.md) | **五阶段建设路线** |
| [08-mvp-scope.md](./08-mvp-scope.md) | 一期 MVP（历史参考） |
| [09-evaluation.md](./09-evaluation.md) | 评估与验证 |
| [10-tech-stack.md](./10-tech-stack.md) | 技术栈 + Agent 层 |
| [DEPLOY.md](./DEPLOY.md) | **Linux 部署指南**（中间件 / Nginx / systemd） |
| [11-palantir-ontology.md](./11-palantir-ontology.md) | Ontology 语义层 |
| [12-ai-native-agents.md](./12-ai-native-agents.md) | **智能体架构分册** |

## 阅读建议

```
首次阅读：DESIGN.md 全文
智能体专题：DESIGN.md §3 + 12-ai-native-agents.md（扩展）
数据接入：07-data-blueprint.md + 08-implementation-phases.md
Linux 部署：DEPLOY.md
投研上手：首页 WorkflowGuide（五步流程）
```

## 文档结构说明

DESIGN.md 按**最终版 IR-OS 方案**编排（非增量修订体例）：

1. 定位 → 双逻辑 → **§3 架构与智能体（分层嵌入）** → 数据 → 本体 → 推理 → 应用 → 流程 → 工程 → 实施 → 评估 → 合规
