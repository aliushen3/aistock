import { Button, Card, Empty, List, Space, Tag, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import type { AlertItem, SectorWorkflowOverviewItem, WorkflowTodo } from "../../lib/api";

type Risk = "high" | "medium" | "low";

interface InboxItem {
  key: string;
  sectorId?: string;
  sectorName?: string;
  message: string;
  count: number;
  risk: Risk;
  route: string;
  action: string;
}

/** 待办类型 → 风险等级（摩擦预算分级，对齐 DESIGN §8.4） */
const TODO_RISK: Record<string, Risk> = {
  sector_not_confirmed: "high",
  pending_candidates: "high",
  bear_case_unrebutted: "high",
  bottleneck_recommendation: "medium",
  serenity_recommendation: "medium",
  knowledge_draft: "medium",
  knowledge_stale: "medium",
  empty_graph: "low",
  no_constituents: "low",
};

const ALERT_RISK: Record<string, Risk> = { high: "high", medium: "medium", info: "low", low: "low" };

const RISK_ORDER: Record<Risk, number> = { high: 0, medium: 1, low: 2 };
const RISK_TAG: Record<Risk, { color: string; label: string }> = {
  high: { color: "red", label: "高风险闸" },
  medium: { color: "orange", label: "中风险" },
  low: { color: "blue", label: "低风险" },
};

function buildInbox(
  overview: SectorWorkflowOverviewItem[],
  globalAlerts: AlertItem[]
): InboxItem[] {
  const items: InboxItem[] = [];
  overview.forEach((s) => {
    (s.pending_todos ?? []).forEach((t: WorkflowTodo, i) => {
      items.push({
        key: `${s.sector_id}_${t.type}_${i}`,
        sectorId: s.sector_id,
        sectorName: s.sector_name,
        message: t.message,
        count: t.count,
        risk: TODO_RISK[t.type] ?? "medium",
        route: t.route,
        action: t.action,
      });
    });
  });
  const seen = new Set(items.map((i) => `${i.sectorId ?? ""}:${i.message}`));
  globalAlerts.forEach((a, i) => {
    if (seen.has(`:${a.message}`)) return;
    items.push({
      key: `global_${a.type}_${i}`,
      message: a.message,
      count: a.count ?? 1,
      risk: ALERT_RISK[a.level] ?? "medium",
      route: "/",
      action: a.action ?? "",
    });
  });
  return items.sort((a, b) => RISK_ORDER[a.risk] - RISK_ORDER[b.risk]);
}

interface Props {
  overview: SectorWorkflowOverviewItem[];
  globalAlerts: AlertItem[];
  loading?: boolean;
  onSelectSector: (sectorId: string) => void;
}

/** 驾驶舱 · 决策收件箱：聚合所有待人工裁决事项，按风险等级排序，直达处理入口 */
export default function DecisionInbox({ overview, globalAlerts, loading, onSelectSector }: Props) {
  const navigate = useNavigate();
  const items = buildInbox(overview, globalAlerts);

  const handle = (item: InboxItem) => {
    if (item.sectorId) onSelectSector(item.sectorId);
    navigate(item.route);
  };

  return (
    <Card
      title={
        <Space>
          <span>决策收件箱</span>
          <Tag color={items.length ? "orange" : "green"}>{items.length} 项待裁决</Tag>
        </Space>
      }
      size="small"
      style={{ marginBottom: 16 }}
      loading={loading}
    >
      {items.length === 0 ? (
        <Empty description="暂无待裁决事项 — Agent 推进中或流程已完成" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          size="small"
          dataSource={items}
          renderItem={(item) => (
            <List.Item
              actions={[
                <Button key="go" size="small" type="link" onClick={() => handle(item)}>
                  去处理 →
                </Button>,
              ]}
            >
              <Space size={8} wrap>
                <Tag color={RISK_TAG[item.risk].color}>{RISK_TAG[item.risk].label}</Tag>
                {item.sectorName && <Tag>{item.sectorName}</Tag>}
                <Typography.Text>{item.message}</Typography.Text>
                {item.count > 1 && (
                  <Typography.Text type="secondary">×{item.count}</Typography.Text>
                )}
              </Space>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
