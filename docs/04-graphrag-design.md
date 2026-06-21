# GraphRAG 推理设计

> **v3.0**：反证（看空）从 GraphRAG 的下游 Level 2 **升格为独立一等环节**——由独立的 `BearCaseAgent` 自带检索、与看多论点等强度对抗，并构成入池硬闸门。GraphRAG 本身聚焦**看多侧综合**；看空侧见 §5、对齐主册 [DESIGN.md §6.4](./DESIGN.md)。
> **v2.0**：检索层已支持 `search_hybrid`（上传研报 + 图谱上下文）；`ReportGraphRAGAgent` 编排化见 [12-ai-native-agents.md](./12-ai-native-agents.md)。

## 1. 定位

GraphRAG 是本系统**定性推理层（L4）**的核心，负责将结构化图谱与非结构化文本融合，生成**可解释、带引用**的投研**看多**逻辑草稿；与之等强对抗的**看空论点（Bear Case）**由独立 `BearCaseAgent` 产出（§5）。两者在入池前并排对照（多空对照视图）。

**禁止**：无 citation 的断言、自动发布、替代人工审核、替研究员回应空头论点。

## 2. 三级推理架构（看多侧）

> 看空（反证）不再是本表的 Level 2，而是由独立 BearCaseAgent 承担（§5）。本表聚焦看多逻辑链的生成与自校验。

```
┌──────────────────────────────────────────────────────────────────┐
│  Level 3  逻辑生成（看多）  赛道Beta + 瓶颈 + 标的 + 预期差/价值捕获摘要 │
├──────────────────────────────────────────────────────────────────┤
│  Level 2  事实校验          claim 数值与图谱 confirmed / 保鲜状态比对  │
├──────────────────────────────────────────────────────────────────┤
│  Level 1  事实推理          图谱多跳查询 + 文档检索验证                │
└──────────────────────────────────────────────────────────────────┘
```

## 3. 检索流程（三阶段）

### Stage 1：意图解析

输入：用户问题或选股任务上下文（赛道、标的、模式）

输出：
```json
{
  "intent": "bottleneck_analysis | serenity_trace | risk_check | report_gen",
  "entities": ["sector_ai_compute", "prod_cowos"],
  "sector": "AI算力",
  "mode": "buy_side | serenity | fusion"
}
```

### Stage 2：混合检索

**2a 图谱子图检索**

```cypher
// 示例：从终端向下游/上游扩展 2 跳
MATCH path = (s:Sector {id: $sector_id})<-[:BELONGS_TO]-(p:Product)
MATCH (p)-[:UPSTREAM_OF|DOWNSTREAM_OF*1..3]-(related:Product)
OPTIONAL MATCH (c:Company)-[:PRODUCES]->(related)
RETURN path, related, c
```

**2b 向量检索**

- 索引：研报 chunk、公告、专家批注
- 检索策略：HyDE 或 实体名 + 赛道名 增强 query
- Top-K：10–20 chunks，按相关度 + 时效加权

**2c 融合上下文**

```
[System] 本体约束 + 输出格式要求 + 禁止幻觉规则
[Graph]  子图 JSON（节点、边、属性、溯源）
[Docs]   检索 chunks（含 source_ref）
[Task]   具体推理任务指令
```

### Stage 3：约束生成

- 温度：0.2–0.4（偏低，减少幻觉）
- **强制输出 JSON + Markdown 双格式**
- 每条 `claim` 必须含 `citations[]`
- 无 citation 的 claim 标记为 `unverified`，前端高亮警告

## 4. 输出 Schema

```json
{
  "report_id": "uuid",
  "status": "draft",
  "sector": "AI算力",
  "mode": "fusion",
  "logic_chain": [
    {
      "step": 1,
      "type": "beta_thesis",
      "claim": "AI算力赛道处于资本开支上行周期",
      "citations": ["prov_001", "prov_002"],
      "confidence": "high"
    },
    {
      "step": 2,
      "type": "bottleneck",
      "claim": "CoWoS封装为当前核心瓶颈环节",
      "citations": ["prov_003"],
      "confidence": "medium",
      "human_confirmed": true
    }
  ],
  "counter_arguments": [
    {
      "risk": "台积电扩产CoWoS产能",
      "severity": "medium",
      "citations": ["prov_004"],
      "mitigation": "扩产周期仍需18个月"
    }
  ],
  "candidates": [
    {
      "stock_code": "688xxx",
      "role": "buy_side_leader",
      "thesis_summary": "..."
    }
  ],
  "unverified_claims": [],
  "generated_at": "2025-06-17T10:00:00Z"
}
```

## 5. 反证：BearCaseAgent（独立一等环节）

> **v3.0 升格。** 反证不再是看多报告内的 `counter_arguments` 附属，而是由**独立 Agent、独立检索、硬闸门**承载——把「反证等强」从口号变成工程约束。对齐主册 [DESIGN.md §6.4](./DESIGN.md)。

### 5.1 独立性原则

- **独立检索**：BearCaseAgent 用 `searchCounterEvidence` 主动找反面证据，**不复用看多 Agent 的检索结果**，规避确认偏误。
- **等强投入**：看空论点与看多逻辑链同等检索深度与 LLM 预算，前端**并排对照**展示。

### 5.2 七项反证维度（逐项必查）

| 维度 | 数据来源 | 触发条件 | 联动 |
|--------|---------|---------|------|
| 技术替代 | 研报、专利、新闻 | 存在成熟替代方案 | — |
| 新增扩产 | 公告、产业链新闻 | 2 年内大量产能释放 | → 瓶颈生命周期 `easing`（主册 §5.7） |
| 需求下滑 | 行业数据、下游出货 | 增速环比转负 | — |
| 估值透支 | PE/PB 分位、研报目标价 | 分位 > 80% | → 闸一 预期差 |
| 政策风险 | 政策库 | 限制性政策 | — |
| 客户集中度 | 财报 | 前五大客户 > 70% | → 闸二 价值捕获 |
| 库存累积 | 行业数据 | 库存周转恶化 | — |

### 5.3 结构化输出（`BearCase` 对象）

```json
{
  "candidate_id": "...",
  "arguments": [
    {
      "risk": "台积电扩产 CoWoS 产能",
      "dimension": "新增扩产",
      "severity": "high",
      "probability": "medium",
      "citations": ["prov_004"],
      "what_would_confirm": "2026 H2 月产能爬坡公告 + 现货价格回落",
      "rebuttal_status": "unrebutted"
    }
  ]
}
```

### 5.4 硬闸门（入池闸三）

- `severity=high` 的空头论点 `rebuttal_status=unrebutted` → **阻断 `ApprovePoolEntry`**（区别于旧版「仅生成告警、不剔除」）。
- 研究员须通过 `RebutBearCase`（正面回应，必填）方可放行；保留人工最终权，但**未回应不得入池**为流程硬约束。
- 进入 `UnrebuttedBearCases` Object Set 与 `bear_case_unrebutted`（high）告警。

## 6. 幻觉防控

| 措施 | 说明 |
|------|------|
| Citation 强制 | 无引用标 `unverified` |
| 图谱事实优先 | 数值以图谱 confirmed 数据为准，LLM 不得编造 |
| 温度限制 | ≤ 0.4 |
| 后处理校验 | 抽取 claim 中数值，与图谱比对 |
| 人工门控 | `status=draft`，审核后变 `published` |

**系统 Prompt 约束（固定前缀）：**

```
你是产业投研助手，不是投资顾问。
- 仅基于提供的【图谱事实】和【文档摘录】推理
- 每个论点必须标注 [ref:N]
- 禁止预测股价涨幅
- 禁止给出买入 / 卖出建议
- 对不确定项明确说「数据不足，需人工核实」
```

## 7. Chunk 策略

| 文档类型 | Chunk 大小 | 重叠 | 元数据 |
|---------|-----------|------|--------|
| 深度研报 | 800–1200 字 | 150 字 | 券商、日期、赛道、页码 |
| 公告 | 按章节 | - | 公司、公告类型、日期 |
| 会议纪要 | 按 Q&A | - | 公司、日期 |
| 专家批注 | 整条 | - | 作者、关联实体 |

## 8. API 设计（草案）

```
POST /api/v1/reasoning/graphrag          # 看多逻辑链草稿
  body: { intent, sector_id, product_ids[], mode, candidate_stocks[] }
  response: SSE 流式 或 完整 JSON

POST /api/v1/reasoning/bearcase          # 看空论点（独立检索）
  body: { candidate_id | sector_id, product_ids[] }
POST /api/v1/candidates/{id}/rebut       # 回应空头论点（RebutBearCase）
  body: { argument_id, rebuttal, operator }

GET  /api/v1/reasoning/reports/{id}
POST /api/v1/reasoning/reports/{id}/review
  body: { action: approve|reject|revise, comments, revisions }
```

## 9. 技术实现

| 组件 | 选型 |
|------|------|
| 编排 | LangChain / 自研 Pipeline |
| LLM | DeepSeek API / GLM-4 API |
| 向量库 | Qdrant |
| 图谱 | Neo4j Python Driver |
| 流式输出 | FastAPI SSE |
