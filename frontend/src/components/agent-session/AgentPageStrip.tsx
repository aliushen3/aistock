import { Card, Typography } from "antd";
import AgentSessionPanel from "./AgentSessionPanel";

interface Props {
  sectorId?: string;
  focus?: string;
  workflowStep?: number;
  pageHint?: string;
  onReload?: () => void;
}

/** 各 Step 页底部 LUI 条（紧凑模式） */
export default function AgentPageStrip({
  sectorId,
  focus,
  workflowStep,
  pageHint,
  onReload,
}: Props) {
  if (!sectorId) {
    return (
      <Card size="small">
        <Typography.Text type="secondary">请先在右上角选择赛道以使用 Agent 对话</Typography.Text>
      </Card>
    );
  }
  return (
    <>
      {pageHint && (
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8, fontSize: 12 }}>
          {pageHint}
        </Typography.Text>
      )}
      <AgentSessionPanel
        sectorId={sectorId}
        focus={focus}
        workflowStep={workflowStep}
        onReload={onReload}
        compact
      />
    </>
  );
}
