# Serenity 逆向溯源算法

## 1. 算法目标

从**已确认高景气**的终端赛道出发，沿产业链图谱**反向遍历** 3–4 层，筛选符合 Serenity 逻辑的小众咽喉环节及对应上市公司。

**输出性质**：候选提示清单，需研究员确认后方可入池。

> **结构性张力（v3.0 必读）**：Serenity 瞄准的「低覆盖、小市值、低成交」标的，恰是**数据最稀、流动性最差、信披最弱**、知识图谱最易幻觉的群体。因此：① 这些标的 `confidence` 默认降一档、强制双源（见 07 §4）；② **「替代难度高 / 不可替代」这类最难的定性判断必须人工确认，禁止 LLM 单独定性**；③ 入池前与买方标的一样须过三道闸（主册 §2.6），且价值捕获与流动性风险权重上调。

## 2. 输入 / 输出

### 输入

```json
{
  "sector_id": "sector_ai_compute",
  "terminal_products": ["prod_gpu", "prod_ai_server"],
  "max_hops": 4,
  "min_hops": 3,
  "config": {
    "max_market_cap_billion": 200,
    "max_analyst_coverage": 5,
    "max_turnover_percentile": 0.3,
    "max_cost_ratio": 0.05,
    "exclude_top_n_by_cap": 3
  }
}
```

### 输出

```json
{
  "paths": [
    {
      "path_id": "path_001",
      "nodes": ["prod_gpu", "prod_pcb", "prod_ccl", "prod_e_glass"],
      "hop_count": 3,
      "niche_product_id": "prod_e_glass",
      "niche_score_hint": 72,
      "companies": [
        {
          "stock_code": "300xxx",
          "name": "某公司",
          "market_cap": 85,
          "analyst_coverage": 2,
          "serenity_tags": ["low_cap", "low_coverage", "niche_material"]
        }
      ]
    }
  ],
  "status": "pending_review"
}
```

## 3. 图遍历伪代码

```python
def serenity_reverse_trace(
    graph,
    terminal_product_ids: list[str],
    min_hops: int = 3,
    max_hops: int = 4,
    config: SerenityConfig,
) -> list[TracePath]:
    """
    从终端产品反向遍历上游，收集所有有效路径。
    """
    all_paths = []

    for terminal_id in terminal_product_ids:
        # BFS/DFS 反向遍历，限制深度
        paths = graph.find_paths(
            start=terminal_id,
            relation="UPSTREAM_OF",
            direction="reverse",
            min_depth=min_hops,
            max_depth=max_hops,
        )

        for path in paths:
            niche_product = path.leaf_node  # 最上游节点

            if not passes_niche_filter(niche_product, config):
                continue

            companies = graph.query(
                "MATCH (c:Company)-[:PRODUCES]->(p:Product {id: $id}) RETURN c",
                id=niche_product.id,
            )

            filtered_companies = [
                c for c in companies
                if passes_company_filter(c, config, sector_id)
            ]

            if filtered_companies:
                all_paths.append(TracePath(
                    nodes=path.nodes,
                    niche_product=niche_product,
                    companies=filtered_companies,
                    hint_score=calc_serenity_hint(path, niche_product, config),
                ))

    # 去重：同一 niche_product 保留最短路径
    return dedupe_by_niche_product(all_paths)
```

## 4. 剪枝规则

### 4.1 产品层剪枝（`passes_niche_filter`）

| 规则 | 条件 | 动作 |
|------|------|------|
| R1 层级 | level in (material, consumable) 且 hop ≥ 2 | 保留 |
| R2 成本占比 | cost_ratio < 5% 或 substitution_difficulty = high | 保留 |
| R3 非终端 | level != terminal | 保留 |
| R4 替代性 | substitution_difficulty = low | **剪枝** |
| R5 已确认小众 | serenity_niche = confirmed | 优先保留 |

### 4.2 公司层剪枝（`passes_company_filter`）

| 规则 | 条件 | 动作 |
|------|------|------|
| C1 市值 | market_cap < max_market_cap | 保留 |
| C2 覆盖度 | analyst_coverage < max_coverage | 保留 |
| C3 拥挤度 | turnover_percentile < max_percentile | 保留 |
| C4 龙头排除 | 赛道市值排名前 exclude_top_n | **剪枝** |
| C5 亏损 | 连续 2 年扣非亏损 | **剪枝**（可配置） |

### 4.3 路径分叉处理

- DAG 存在多父节点时：**保留所有有效路径**，分别展示
- 同一产品多路径到达：去重时保留**跳数最短**路径
- 跳数不足 min_hops：丢弃

## 5. Serenity 提示分（Hint Score）

**非投资决策分**，仅用于候选排序。

```
serenity_hint = (
    niche_fit      * 0.30   # 小众刚需匹配度（规则命中数/总规则数）
  + supply_rigidity * 0.25   # 供给刚性（扩产周期、认证）
  + low_attention   * 0.25   # 低关注（覆盖度、拥挤度反向）
  + path_quality    * 0.20   # 路径质量（跳数适中、链条清晰）
)
```

## 6. 与买方逻辑的衔接

| 场景 | 处理 |
|------|------|
| 同一产品已是 `bottleneck_confirmed` | 同时进入融合池，标注「双逻辑共振」 |
| 买方龙头 + Serenity 小众配套 | 生成组合建议草稿 |
| 终端龙头 | Serenity 自动排除，买方逻辑可保留 |
| 小众环节但利润被大客户攫取 | 价值捕获闸（主册 §2.6 闸二）判 `no/partial` → 降级或标注「利润不在此环节」 |

## 7. Neo4j 查询示例

```cypher
// 反向 3-4 跳上游路径
MATCH path = (terminal:Product {id: $terminal_id})
             <-[:UPSTREAM_OF*3..4]-(niche:Product)
WHERE niche.level IN ['material', 'consumable']
  AND niche.substitution_difficulty = 'high'
  AND (niche.cost_ratio < 0.05 OR niche.cost_ratio IS NULL)
WITH path, niche
MATCH (c:Company)-[:PRODUCES]->(niche)
WHERE c.market_cap < $max_cap
  AND c.analyst_coverage < $max_coverage
RETURN path, niche, collect(c) AS companies
ORDER BY length(path)
LIMIT 50
```

## 8. 前端展示

- 高亮逆向路径（终端 → 小众环节）
- 节点标注 Serenity 标签
- 每条路径可「确认入池 / 否决」
- 显示剪枝被排除原因（可展开）
