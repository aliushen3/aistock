# GraphRAG 推理设计

## 1. 定位

GraphRAG 是本系统**定性推理层（L3）**的核心，负责将结构化图谱与非结构化文本融合，生成**可解释、可反驳、带引用**的投研逻辑草稿。

**禁止**：无 citation 的断言、自动发布、替代人工审核。

## 2. 三级推理架构

```
┌─────────────────────────────────────────────────────────┐
│  Level 3  逻辑生成推理   赛道Beta + 瓶颈 + 标的 + 风险总结  │
├─────────────────────────────────────────────────────────┤
│  Level 2  反证推理       技术替代 / 扩产 / 需求下滑 / 估值  │
├─────────────────────────────────────────────────────────┤
│  Level 1  事实推理       图谱多跳查询 + 文档检索验证      │
└─────────────────────────────────────────────────────────┘
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

## 5. 反证推理 Checklist

每次生成报告**必须**逐项检查，结果写入 `counter_arguments`：

| 检查项 | 数据来源 | 触发条件 |
|--------|---------|---------|
| 技术替代 | 研报、专利、新闻 | 存在成熟替代方案 |
| 新增扩产 | 公告、产业链新闻 | 2 年内大量产能释放 |
| 需求下滑 | 行业数据、下游出货 | 增速环比转负 |
| 估值透支 | PE/PB 分位、研报目标价 | 分位 > 80% |
| 政策风险 | 政策库 | 限制性政策 |
| 客户集中度 | 财报 | 前五大客户 > 70% |
| 库存累积 | 行业数据 | 库存周转恶化 |

未通过项不自动剔除标的，而是生成**风险告警**供研究员判断。

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
POST /api/v1/reasoning/graphrag
  body: { intent, sector_id, product_ids[], mode, candidate_stocks[] }
  response: SSE 流式 或 完整 JSON

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
