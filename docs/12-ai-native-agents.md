# AI Native 投研操作系统与智能体架构

> **分册** — 与 [DESIGN.md §3 总体架构与智能体体系](./DESIGN.md#3-总体架构与智能体体系) 保持一致。冲突以总册为准。

## 1. 定位

**IR-OS** = Ontology（确定性基座）+ Knowledge Graph + Vector RAG + **Multi-Agent** + Human-in-the-Loop
**三条贯穿主线**：反证优先 · 知识保鲜 · 预期差与价值捕获。

智能体只产出 **提案（Proposal）**；生效须经 **Ontology Action** 人工确认。

## 2. 投研智能体矩阵（v3.0）

> 按「LLM 是否不可替代」分两类：**LLM 真正不可替代的只有非结构化抽取与多空叙事综合**，其余应是透明确定的 Pipeline。ReAct 仅用于 A 类。对齐主册 [DESIGN.md §3.4](./DESIGN.md)。

### A 类 · 真 LLM 智能体（ReAct，LLM 不可替代）

| Agent | 职责 | 人工 Action |
|-------|------|-------------|
| KnowledgeIngestAgent | 非结构化抽取（PDF/公告 → 三元组） | CalibrateChain |
| ReportGraphRAGAgent | 看多逻辑链综合 | PublishReport |
| **BearCaseAgent** 🆕 | 看空对抗（独立检索、等强论点） | RebutBearCase |

### B 类 · 确定性 Pipeline（规则为主，LLM 仅兜底/解释）

| Agent/Pipeline | 本质 | 人工 Action |
|-------|------|-------------|
| SectorRecommendAgent | 信号扫描 + 主题抽取（LLM 增强） | ConfirmSectorBeta |
| BottleneckScoutAgent | 提示分规则引擎扫描 | ConfirmBottleneck |
| SerenityPathAgent | 图遍历 + 剪枝 | ConfirmSerenityNiche |
| CandidateFusionAgent | 集合运算 + 排序 + 三道闸汇合 | ApprovePoolEntry |
| MonitorWatchAgent | 规则告警 + 保鲜/生命周期状态机驱动 | ConfirmBottleneckEasing 等 |

> B 类沿用 "Agent" 仅为前端一致性；实现优先确定性 Pipeline，引入 LLM 时标注 `llm_assisted=true`。

## 3. ReAct 运行时

1. 注入 `TOOL_SPECS` + focus/query
2. 循环（≤5 轮）：`{thought, action, action_input}` → `execute_tool()` → 观察
3. 结束：`{thought, final_answer}` → 校验 → `ont_*_recommendation` 落库
4. 降级：LLM 失败 → 规则扫描
5. 后置：Object Set 告警推送

共享工具见 `backend/app/agents/sector_agent_tools.py`（将扩展为 `agents/tools/`）。

## 4. 用户 5 步上手

| 步骤 | 动作 | 页面 |
|------|------|------|
| ① 发现赛道 | 运行 SectorAgent → 采纳 → 确认景气 | 首页 |
| ② 研判产业 | 上传研报 → 看板 + 图谱 | 知识抽取、看板、图谱 |
| ③ 筛选标的 | 候选池 + 智能诊断 | 候选池、诊断 |
| ④ 论证报告 | GraphRAG 草稿 → 审核 | 投研报告 |
| ⑤ 确认入池 | 人工入池 + 审计 | 候选池、审计 |

前端组件：`frontend/src/components/WorkflowGuide.tsx`

## 5. API

| 方法 | 路径 |
|------|------|
| POST | `/api/v1/agents/sector-recommend/run` |
| GET | `/api/v1/agents/sector-recommendations` |
| POST | `/api/v1/agents/sector-recommendations/{id}/adopt` |
| POST | `/api/v1/knowledge/upload` |

## 6. 建设路线（阶段 C）

C1 KnowledgeIngestAgent（LLM ReAct）✅ → … → C7 动态观察清单 ✅（`watchlist_service`）

阶段 F（v3.0）新增 BearCaseAgent、保鲜状态机、预期差/价值捕获三道闸，详见 [DESIGN.md §10.4](./DESIGN.md)。
