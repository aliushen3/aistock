# 建设阶段与范围（v2.0）

> 与 [DESIGN.md §10 实施路径](./DESIGN.md#10-实施路径与实现状态) 一致。

## 阶段总览

| 阶段 | 名称 | 状态 | 目标 |
|------|------|------|------|
| **0** | 演示基座 | ✅ 完成 | 单赛道端到端 PoC + 赛道推荐 Agent |
| **A** | 数据底座接通 | ✅ 骨架完成 | ODS + 适配器 stub + embedding 框架 |
| **B** | 知识生产流水线 | ✅ 骨架完成 | KnowledgeIngestAgent ReAct |
| **C** | 智能研判增强 | 🔶 进行中 | 多 Agent + Orchestrator 已上线 |
| **F** | 三主线落地（v3.0） | ⬜ 规划 | 反证/保鲜/预期差成为主干 |
| **D** | 多赛道与组织协同 | ⏳ | 角色分权、报告导出 |
| **E** | 商用运营 | ⏳ | KPI、NL 问答、高可用 |

## 阶段 0 交付（已完成）

- Ontology Action / Object Set / 门控闭环
- 双逻辑候选池、GraphRAG、Serenity、研报上传、SectorRecommendAgent（ReAct）
- 首页投研流程指引（WorkflowGuide）

## 阶段 A 交付（已完成）

- [x] `ods_*` 四表、`adapters/`（mock / wind / cninfo stub）
- [x] Celery Beat、看板读 ODS、公告同步
- [x] embedding 框架（`LLM_API_KEY` 存在时启用 API，否则伪向量）
- [ ] Wind/巨潮 live API

## 阶段 B 交付（已完成）

- [x] `extract_with_llm` + 规则降级
- [x] `KnowledgeIngestAgent` ReAct + API

## 阶段 C 交付（已完成）

- [x] BottleneckScoutAgent + 提案表 + 告警
- [x] InvestResearchOrchestrator（七步门控串联）
- [x] SerenityPathAgent 封装
- [x] ReportGraphRAGAgent 独立入口
- [x] MonitorWatchAgent + Celery Beat
- [x] C7 动态观察清单（去除写死 `WATCH_SECTORS`，`GET /agents/watchlist`）

## 阶段 F 交付（v3.0 三主线，规划）

> 按杠杆排序，对应主册 [DESIGN.md §10.4](./DESIGN.md)。

- [ ] F1 BearCaseAgent + 独立反证检索 + 入池硬闸门（P0）
- [ ] F2 保鲜状态机 + 瓶颈生命周期（easing/expired）（P0）
- [ ] F3 `edgeSignal` + `valueCapture` + 入池三道闸（P0）
- [ ] F4 提示分校准闭环 + 结果回溯表（P1）
- [ ] F5 多源交叉 / 卖方去偏 / 自反性叙事打标（P1）
- [ ] F6 Agent 矩阵 A/B 分类收敛（P1）
- [ ] F7 摩擦预算分级（高/中/低风险闸）（P2）
- [ ] F8 结果回溯评估维 + 盲测复盘（P2）
- [ ] F9 A 股反身性 / 解禁 / 小市值数据张力处理（P2）

## 不做

GNN、自动交易、LLM 微调、Flink、NebulaGraph、移动端。

## 验收

阶段 A 完成标志：看板指标来自 `ods_*` 表，适配器可切换 mock/real。
