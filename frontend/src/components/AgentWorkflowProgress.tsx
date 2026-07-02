import { Steps, Tooltip, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import type { WorkflowPhase, WorkflowStep } from "../lib/api";

const STATUS_MAP: Record<string, "finish" | "process" | "wait" | "error"> = {
  done: "finish",
  active: "process",
  blocked: "error",
  pending: "wait",
};

interface Props {
  phases?: WorkflowPhase[];
  currentPhase?: number;
  /** 兼容旧调用：仅有七步数据时降级渲染 */
  steps?: WorkflowStep[];
  currentStep?: number;
  compact?: boolean;
}

export default function AgentWorkflowProgress({
  phases,
  currentPhase,
  steps,
  currentStep,
  compact,
}: Props) {
  const navigate = useNavigate();

  if (phases?.length) {
    const items = phases.map((p) => ({
      title: compact ? `${p.phase_number}` : p.title,
      description: compact ? undefined : (
        <Tooltip title={p.block_reason || p.description}>
          <Typography.Text type={p.pending_count > 0 ? "warning" : "secondary"} style={{ fontSize: 12 }}>
            {p.pending_count > 0 ? `${p.pending_count} 待办` : p.description}
          </Typography.Text>
        </Tooltip>
      ),
      status: STATUS_MAP[p.status] ?? "wait",
      onClick: () => navigate(p.cta_route),
    }));
    const current = (currentPhase ?? 1) - 1;
    return (
      <div style={{ marginBottom: 16 }}>
        <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
          投研五阶段（当前：{phases[current]?.title ?? "—"}）
        </Typography.Text>
        <Steps
          size={compact ? "small" : "default"}
          current={current}
          items={items}
          responsive
          style={{ cursor: "pointer" }}
        />
      </div>
    );
  }

  if (!steps?.length) return null;
  const items = steps.map((s) => ({
    title: compact ? undefined : s.title,
    description: compact ? (
      <Tooltip title={`${s.title}${s.block_reason ? ` — ${s.block_reason}` : ""}`}>
        <Typography.Text style={{ fontSize: 11 }}>{s.step_number}</Typography.Text>
      </Tooltip>
    ) : (
      <Tooltip title={s.block_reason || s.agent}>
        <span>
          {s.pending_count > 0 && (
            <Typography.Text type="warning"> ({s.pending_count} 待办)</Typography.Text>
          )}
        </span>
      </Tooltip>
    ),
    status: STATUS_MAP[s.status] ?? "wait",
    onClick: () => navigate(s.cta_route),
  }));

  return (
    <div style={{ marginBottom: 16 }}>
      <Typography.Text strong style={{ display: "block", marginBottom: 8 }}>
        Agent 工作流（当前 Step {currentStep}）
      </Typography.Text>
      <Steps
        size={compact ? "small" : "default"}
        current={(currentStep ?? 1) - 1}
        items={items}
        responsive
        style={{ cursor: "pointer" }}
      />
    </div>
  );
}
