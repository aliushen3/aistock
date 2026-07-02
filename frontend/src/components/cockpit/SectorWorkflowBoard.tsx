import { Badge, Button, Card, Space, Steps, Table, Tag, Tooltip, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import type { SectorWorkflowOverviewItem, WorkflowPhase } from "../../lib/api";

const PHASE_STATUS: Record<string, "finish" | "process" | "wait" | "error"> = {
  done: "finish",
  active: "process",
  blocked: "error",
  pending: "wait",
};

function PhaseMiniSteps({ phases, current }: { phases: WorkflowPhase[]; current: number }) {
  return (
    <Steps
      size="small"
      current={current - 1}
      items={phases.map((p) => ({
        title: (
          <Tooltip title={`${p.title}${p.block_reason ? ` — ${p.block_reason}` : ""}`}>
            <span style={{ fontSize: 12 }}>{p.title}</span>
          </Tooltip>
        ),
        status: PHASE_STATUS[p.status] ?? "wait",
      }))}
      responsive={false}
      style={{ minWidth: 340 }}
    />
  );
}

interface Props {
  items: SectorWorkflowOverviewItem[];
  activeSectorId?: string | null;
  loading?: boolean;
  resumingId?: string | null;
  onSelect: (sectorId: string) => void;
  onResume: (sectorId: string) => void;
}

/** 驾驶舱 · 赛道工作流看板：多赛道并行，一行一个赛道，展示五阶段进度与卡点 */
export default function SectorWorkflowBoard({
  items,
  activeSectorId,
  loading,
  resumingId,
  onSelect,
  onResume,
}: Props) {
  const navigate = useNavigate();

  const enterPhase = (item: SectorWorkflowOverviewItem) => {
    onSelect(item.sector_id);
    const active = item.phases.find((p) => p.phase_number === item.current_phase);
    navigate(active?.cta_route ?? "/");
  };

  return (
    <Card title="在研赛道 · 五阶段进度" size="small" style={{ marginBottom: 16 }}>
      <Table
        size="small"
        rowKey="sector_id"
        loading={loading}
        dataSource={items}
        pagination={false}
        onRow={(r) => ({
          onClick: () => onSelect(r.sector_id),
          style: {
            cursor: "pointer",
            background: r.sector_id === activeSectorId ? "rgba(22,119,255,0.06)" : undefined,
          },
        })}
        columns={[
          {
            title: "赛道",
            dataIndex: "sector_name",
            width: 170,
            render: (name: string, r: SectorWorkflowOverviewItem) => (
              <Space size={4}>
                <Typography.Text strong>{name || r.sector_id}</Typography.Text>
                {r.sector_confirmed ? (
                  <Tag color="green">已确认</Tag>
                ) : (
                  <Tag color="orange">待确认</Tag>
                )}
              </Space>
            ),
          },
          {
            title: "阶段进度",
            render: (_: unknown, r: SectorWorkflowOverviewItem) => (
              <PhaseMiniSteps phases={r.phases} current={r.current_phase} />
            ),
          },
          {
            title: "当前卡点",
            width: 220,
            render: (_: unknown, r: SectorWorkflowOverviewItem) => {
              const active = r.phases.find((p) => p.phase_number === r.current_phase);
              const allDone = r.phases.every((p) => p.status === "done");
              if (allDone) return <Tag color="green">流程完成 · 跟踪中</Tag>;
              return (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {r.blocking_point || active?.description || "—"}
                </Typography.Text>
              );
            },
          },
          {
            title: "待办",
            width: 70,
            render: (_: unknown, r: SectorWorkflowOverviewItem) => (
              <Badge count={r.pending_total} showZero color={r.pending_total ? "orange" : "green"} />
            ),
          },
          {
            title: "操作",
            width: 210,
            render: (_: unknown, r: SectorWorkflowOverviewItem) => (
              <Space>
                <Button size="small" onClick={(e) => { e.stopPropagation(); enterPhase(r); }}>
                  进入当前阶段
                </Button>
                <Tooltip
                  title={
                    r.resume_steps.length
                      ? `将自动运行：${r.resume_steps.join(" → ")}，到人工门控点暂停`
                      : "无可自动推进的步骤（等待人工裁决或已完成）"
                  }
                >
                  <Button
                    size="small"
                    type="primary"
                    disabled={!r.resume_steps.length || !r.sector_confirmed}
                    loading={resumingId === r.sector_id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onResume(r.sector_id);
                    }}
                  >
                    一键投研 · 续跑
                  </Button>
                </Tooltip>
              </Space>
            ),
          },
        ]}
      />
    </Card>
  );
}
