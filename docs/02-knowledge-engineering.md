# 知识工程蓝图

## 1. 知识工程在全系统中的位置

本系统的**核心资产是知识**，而非模型或因子。技术栈服务于知识的获取、表示、融合、推理、演化与评估。

```
知识获取 → 知识表示 → 知识融合 → 知识推理 → 知识演化 → 知识评估
   ↑                                                      |
   └──────────────── 人工校准反馈 ←─────────────────────────┘
```

| 阶段 | 目标 | 一期交付 |
|------|------|---------|
| 获取 | 从多源数据抽取结构化知识 | LLM 抽取 + 人工导入 |
| 表示 | OWL 本体 + Neo4j 实例化 | 核心本体 v1.0 |
| 融合 | 多源冲突消解、实体对齐 | 冲突仲裁规则 v1 |
| 推理 | 图查询 + 规则提示 + GraphRAG | 规则引擎 + GraphRAG |
| 演化 | 版本管理、增量更新 | Git + 版本表 |
| 评估 | 质量 KPI、复盘反馈 | 评估看板 v1 |

## 2. 知识表示层

### 2.1 本体（Ontology）

| 组件 | 技术 | 说明 |
|------|------|------|
| 建模工具 | Protégé | 可视化编辑 OWL |
| 运行时 | owlready2 (Python) | 约束校验、分类推理 |
| 标准参考 | FIBO 金融本体子集 | 公司、证券等基础概念 |
| 领域扩展 | 自定义产业链本体 | 产品、赛道、事件、瓶颈、Serenity 标签 |

### 2.2 知识图谱（Knowledge Graph）

| 存储 | Neo4j 5.x |
|------|-----------|
| 节点类型 | Product, Company, Sector, Event |
| 关系类型 | UPSTREAM_OF, DOWNSTREAM_OF, PRODUCES, SUPPLIES, BELONGS_TO, TRIGGERS |
| 属性 | 见原方案字段规范 + 知识元数据（见 2.3） |

> **溯源/研判的存储归属**：证据（Evidence）与人工研判（Judgment）统一落在 **PostgreSQL**（见 §3.2 `knowledge_assertion` / `knowledge_provenance`），不在 Neo4j 中另建 `Evidence`/`Judgment` 节点，避免双套溯源模型。Neo4j 仅保留产业拓扑事实与指向断言的 `assertion_id`。

**核心对象属性（Object Properties）**

| 关系 | 域 → 值域 | 说明 |
|------|----------|------|
| UPSTREAM_OF | Product → Product | 上游原材料 |
| DOWNSTREAM_OF | Product → Product | 下游应用 |
| PRODUCES | Company → Product | 公司主营生产 |
| BELONGS_TO | Product → Sector | 所属赛道 |
| SUPPLIES | Company → Company | 供应链 |
| TRIGGERS | Event → Product | 事件驱动 |

### 2.3 知识元数据（每条知识必带）

```json
{
  "knowledge_id": "uuid",
  "entity_type": "Product",
  "entity_id": "prod_cowos",
  "property": "expansion_cycle_months",
  "value": 24,
  "confidence": 0.85,
  "source_type": "research_report",
  "source_ref": "研报标题/页码/URL",
  "source_date": "2025-03-15",
  "extracted_by": "llm_v1",
  "verified_by": "analyst_zhang",
  "verified_at": "2025-03-20",
  "status": "confirmed",
  "ontology_version": "1.2.0"
}
```

## 3. 知识溯源（Provenance）

### 3.1 原则

- **无溯源不展示**：前端展示的任何事实属性必须可点击查看来源
- **多源并存**：同一属性多源冲突时，全部保留并标注优先级
- **推理可追溯**：GraphRAG 输出每条论断绑定 citation 列表

### 3.2 溯源数据模型（PostgreSQL）

```sql
-- 知识断言表
CREATE TABLE knowledge_assertion (
  id UUID PRIMARY KEY,
  entity_type VARCHAR(32),
  entity_id VARCHAR(64),
  property VARCHAR(64),
  value JSONB,
  confidence DECIMAL(3,2),
  status VARCHAR(16),  -- draft / pending / confirmed / rejected / deprecated
  ontology_version VARCHAR(16),
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
);

-- 溯源表
CREATE TABLE knowledge_provenance (
  id UUID PRIMARY KEY,
  assertion_id UUID REFERENCES knowledge_assertion(id),
  source_type VARCHAR(32),  -- report / announcement / expert / llm
  source_ref TEXT,
  source_date DATE,
  excerpt TEXT,
  created_at TIMESTAMPTZ
);
```

## 4. 知识版本管理

### 4.1 版本策略

| 对象 | 版本方式 |
|------|---------|
| OWL 本体文件 | Git 管理，`ontology/versions/vX.Y.Z/` |
| 图谱快照 | Neo4j 定期 dump + 版本号 |
| 赛道链条 | 每次专家校准产生新版本，旧版标记 deprecated |
| 配置规则 | Git + 环境变量 |

### 4.2 变更流程

```
草稿(draft) → 待审(pending) → 已确认(confirmed)
                    ↓
              驳回(rejected) → 修正后重新提交
已确认 → 新证据冲突 → 待复核 → 更新或 deprecated
```

### 4.3 向后兼容

- 本体新增类/属性：minor 版本升级
- 删除或重定义约束：major 版本，需迁移脚本
- 图谱查询 API 携带 `ontology_version` 参数

## 5. 知识冲突消解

### 5.1 冲突类型

| 类型 | 示例 | 策略 |
|------|------|------|
| 数值冲突 | 产能数据 A 源 100 万，B 源 120 万 | 按数据源优先级取主值，副值存 alternate |
| 关系冲突 | LLM 抽取 A 上游 B，专家认定上游 C | 专家确认覆盖 LLM |
| 时效冲突 | 旧研报扩产周期 12 月，新公告 24 月 | 新数据优先，旧数据 deprecated |
| 逻辑冲突 | 标为瓶颈但需求下滑 | 触发反证告警，人工复核 |

### 5.2 数据源优先级与权重（默认，可配置）

优先级顺序：

```
专家确认 > 公司公告 > 行业协会 > 头部券商研报 > 其他研报 > LLM 抽取
```

数值化权重（用于置信度打分 = 来源权重 × 抽取置信度）：

| 来源类型 | 权重 |
|---------|------|
| 公司公告 / 招股书 | 1.0 |
| 行业协会 / 海关数据 | 0.9 |
| 券商深度研报 | 0.85 |
| 第三方数据商 | 0.8 |
| 新闻舆情 | 0.6 |
| 博主 / 非正式来源 | 0.4（默认进审核队列） |

### 5.3 实体对齐（Entity Alignment）

同一实体的多种别名（数据商代码、研报简称、口语名）统一映射到 canonical_id，维护 `entity_alias` 表：

```sql
CREATE TABLE entity_alias (
  canonical_id VARCHAR(64),   -- 如 product:hbm
  alias_name   TEXT,          -- 如 高带宽存储器
  source       VARCHAR(32),   -- wind / report / manual
  resolved_at  TIMESTAMPTZ,
  PRIMARY KEY (canonical_id, alias_name, source)
);
```

## 6. 专家校准工作流

### 6.1 角色

| 角色 | 权限 |
|------|------|
| 产业研究员 | 校准链条、确认/否决瓶颈标签、批注报告 |
| 资深分析师 | 二审争议知识、确认入池 |
| 知识管理员 | 本体版本发布、数据源配置 |
| 只读用户 | 查看图谱与报告 |

### 6.2 校准任务类型

1. **链条校准**：新赛道或 LLM 抽取的上下游关系
2. **瓶颈确认**：`bottleneck_hint` → `bottleneck_confirmed`
3. **小众确认**：`serenity_niche` 人工确认
4. **冲突仲裁**：多源矛盾断言

### 6.3 SLA 建议

| 任务 | 时限 |
|------|------|
| 新赛道链条初审 | 3 个工作日 |
| 瓶颈确认 | 1 个工作日 |
| 冲突仲裁 | 2 个工作日 |

### 6.4 校准 UI 能力（后台模块）

- 图谱上直接编辑/删除/新增关系
- 侧栏展示溯源与冲突
- 原文对照（左：证据摘录 / 右：抽取结果），一键确认/修改/驳回
- 批注与变更理由（必填），驳回理由写入审计日志
- 变更自动写入 `knowledge_assertion` 并同步 Neo4j

### 6.5 双人复核（高级裁定）

- 瓶颈标签升级为 `bottleneck_confirmed`、标的入正式池等高影响操作，需**第二位高级研究员 approve** 方可生效
- 双人复核记录（一审人、二审人、时间、意见）写入审计日志

## 7. 知识质量 KPI

| 指标 | 定义 | 目标（一期） |
|------|------|-------------|
| 链条完整度 | 已确认赛道中，终端到上游材料路径覆盖率 | ≥ 90% |
| 抽取准确率 | 人工抽检三元组正确率 | ≥ 85% |
| 溯源覆盖率 | 已展示属性中有溯源的比例 | 100% |
| 校准及时率 | SLA 内完成的任务占比 | ≥ 95% |
| 冲突未决率 | 冲突断言未仲裁占比 | < 5% |
| 人工修正回写率 | 研究员修正后写入知识库的比例 | 100% |

## 8. 知识获取流水线

```
原始文档(PDF/HTML)
    ↓
文档解析 (MinIO 存储)
    ↓
LLM 三元组抽取 (Prompt + 本体约束)
    ↓
规则校验 (owlready2 约束检查)
    ↓
写入 draft 状态
    ↓
专家校准队列
    ↓
confirmed → 同步 Neo4j + 向量库
```

## 9. 知识演化与闭环

```
投研结论发布
    ↓
产业事件监控（扩产、降价、认证）
    ↓
触发知识复核任务
    ↓
研究员更新/废弃知识
    ↓
（可选）案例库沉淀：历史瓶颈案例 → CBR 检索
```

### 案例推理库（CBR）结构

```json
{
  "case_id": "case_optical_module_2023",
  "sector": "光模块",
  "bottleneck_product": "EML芯片",
  "trigger_events": ["800G放量", "产能紧缺"],
  "outcome_narrative": "瓶颈持续18个月后缓解",
  "lessons": ["设备交付周期是核心变量"],
  "related_entities": ["prod_eml", "company_xxx"]
}
```

用途：GraphRAG 推理时检索类似历史案例，辅助定性判断（**非预测收益**）。一期建议预置 3 条复盘案例：

1. 2020–2021 光伏硅料
2. 2022–2023 光模块 / AI 算力
3. 2021–2022 锂电隔膜

## 10. 一期知识工程交付清单

- [ ] 核心本体 `core.ttl` + 约束 `constraints.ttl`
- [ ] 单赛道（AI 算力 / 光模块）完整拓扑
- [ ] LLM 抽取 pipeline + 校准后台
- [ ] 溯源（`knowledge_assertion` / `knowledge_provenance`）与查询
- [ ] 知识版本管理与 CHANGELOG
- [ ] 3 条历史案例入库
