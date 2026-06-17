# 瓶颈提示分规则引擎

> 替代原方案 GNN 打分。一期使用**透明可审计的规则引擎**，输出「瓶颈提示分（Hint Score）」，仅供排序与关注提示。

## 1. 设计原则

- **可解释**：每个分项可展开查看命中规则与数据来源
- **非决策性**：分数不触发自动入池
- **可配置**：权重与阈值存配置文件，版本化管理
- **需人工确认**：≥70 分仅打 `bottleneck_hint`，人工确认后升为 `bottleneck_confirmed`

## 2. 计算公式

```
bottleneck_hint_score = (
    supply_rigidity  * W1   # 默认 0.30
  + tech_barrier     * W2   # 默认 0.25
  + supply_demand_gap * W3  # 默认 0.25
  + concentration    * W4   # 默认 0.20
)

其中各分项均为 0-100 的标准化分
```

## 3. 分项规则

### 3.1 供给刚性（supply_rigidity）

| 指标 | 分段评分 |
|------|---------|
| 扩产周期（月） | >24→100, 18-24→80, 12-18→50, <12→20 |
| 海外供给依赖 | 是→+20（上限100） |
| 产能利用率 | >90%→+15 |

### 3.2 技术壁垒（tech_barrier）

| 指标 | 分段评分 |
|------|---------|
| 技术壁垒等级 | 极高→100, 高→75, 中→50, 低→20 |
| 客户认证周期（月） | ≥24→100, 12-24→70, <12→30 |
| 替代难度 | 高→+20, 中→+10 |

### 3.3 供需缺口（supply_demand_gap）

| 指标 | 分段评分 |
|------|---------|
| 需求增速 - 产能增速 | >20pp→100, 10-20→75, 0-10→50, <0→10 |
| 涨价持续性（季度） | ≥3→+20, 2→+10 |
| 库存状态 | 去库存→+15, 累库→-20 |

### 3.4 格局集中度（concentration）

| 指标 | 分段评分 |
|------|---------|
| CR4 | >80%→100, 60-80%→80, 40-60%→50, <40%→20 |
| 新玩家准入 | 极难→+20, 一般→0, 容易→-20 |

## 4. 提示等级

| 分数区间 | 标签 | 含义 | 系统动作 |
|---------|------|------|---------|
| ≥ 70 | `hint_high` | 高提示 | 推荐研究员复核，可申请 `bottleneck_confirmed` |
| 50–69 | `hint_medium` | 中提示 | 列入观察 |
| 30–49 | `hint_low` | 低提示 | 仅展示 |
| < 30 | - | 无提示 | 不特别标注 |

## 5. 实现方式

```python
# backend/app/services/hint_score.py

@dataclass
class HintScoreResult:
    total: float
    supply_rigidity: float
    tech_barrier: float
    supply_demand_gap: float
    concentration: float
    hit_rules: list[dict]      # 命中规则明细
    data_sources: list[str]    # 溯源 ID 列表
    hint_level: str            # hint_high | hint_medium | hint_low

def calc_bottleneck_hint(product: ProductNode, config: ScoreConfig) -> HintScoreResult:
    """规则引擎主入口，所有分项可审计。"""
    ...
```

## 6. 配置示例

```yaml
# config/hint_score.yaml
version: "1.0.0"
weights:
  supply_rigidity: 0.30
  tech_barrier: 0.25
  supply_demand_gap: 0.25
  concentration: 0.20
thresholds:
  hint_high: 70
  hint_medium: 50
  hint_low: 30
```

## 7. 与 GNN 的演进路径

| 阶段 | 方案 |
|------|------|
| 一期 | 规则引擎 |
| 二期 | 规则 + 案例相似度（CBR）加权 |
| 三期（可选） | 引入 GNN 作为**辅助分项**，权重 ≤ 20%，且必须可解释 |

**GNN 不得作为一期方案。**
