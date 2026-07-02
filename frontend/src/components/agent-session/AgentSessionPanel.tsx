import { useEffect, useRef, useState } from "react";
import { Badge, Button, Card, Drawer, Space, Spin, Tag, Typography } from "antd";
import { AppstoreOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import AgentChatInput from "./AgentChatInput";
import AgentIntentChips from "./AgentIntentChips";
import AgentMessageList from "./AgentMessageList";
import UIBlockRenderer from "./UIBlockRenderer";
import { useAgentSession } from "./useAgentSession";
import type { AlertItem, SectorWorkflowStatus, WorkflowTodo } from "../../lib/api";

interface Props {
  sectorId?: string;
  sectorName?: string;
  /** 意图上下文（如观察清单选中的主题），不再渲染为独立输入框 */
  focus?: string;
  workflowStep?: number;
  workflowStatus?: SectorWorkflowStatus | null;
  pendingTodos?: WorkflowTodo[];
  alerts?: AlertItem[];
  resumeSteps?: string[];
  onReload?: () => void;
  compact?: boolean;
}

export default function AgentSessionPanel({
  sectorId,
  sectorName,
  focus,
  workflowStep,
  workflowStatus,
  pendingTodos,
  alerts,
  resumeSteps,
  onReload,
  compact,
}: Props) {
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const prevBlockCount = useRef(0);
  const wasRunning = useRef(false);

  const session = useAgentSession(
    {
      sectorId,
      focus: focus?.trim() || undefined,
      workflowStep,
      workflowStatus,
      onNavigate: (p) => navigate(p),
      pendingTodos,
      alerts,
      resumeSteps,
    },
    onReload
  );

  const guiSession = {
    adoptSector: session.adoptSector,
    dismissSector: session.dismissSector,
    dismissBottleneck: session.dismissBottleneck,
    confirmSerenity: session.confirmSerenity,
    dismissSerenity: session.dismissSerenity,
    rebutBear: session.rebutBear,
    runBlockAction: session.runBlockAction,
    handleTodoAction: session.handleTodoAction,
    confirmSectorBeta: session.confirmSectorBeta,
    navigate: session.navigate,
  };

  const blockCount = session.uiBlocks.length;
  const hasGui = blockCount > 0;

  useEffect(() => {
    if (blockCount > prevBlockCount.current && blockCount > 0) {
      setDrawerOpen(true);
    }
    prevBlockCount.current = blockCount;
  }, [blockCount]);

  useEffect(() => {
    if (wasRunning.current && !session.running && blockCount > 0) {
      setDrawerOpen(true);
    }
    wasRunning.current = session.running;
  }, [session.running, blockCount]);

  const title = workflowStep
    ? `Agent 会话（Step ${workflowStep}${sectorName ? ` · ${sectorName}` : ""}）`
    : "Agent 会话";

  return (
    <>
      <Card
        title={title}
        extra={
          <Space size="small">
            {hasGui && (
              <Badge count={blockCount} size="small" offset={[-2, 2]}>
                <Button
                  size="small"
                  icon={<AppstoreOutlined />}
                  type={drawerOpen ? "primary" : "default"}
                  onClick={() => setDrawerOpen((v) => !v)}
                >
                  结果面板
                </Button>
              </Badge>
            )}
            {session.sessionId ? (
              <Button type="link" size="small" onClick={() => session.resetSession()}>
                新会话
              </Button>
            ) : null}
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <Spin spinning={session.running}>
          <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
            LUI — 意图理解与对话{session.sessionId ? " · 已持久化" : ""}
            {hasGui ? " · 结构化结果在右侧抽屉" : ""}
          </Typography.Text>

          <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
            当前赛道：<Tag color="blue">{sectorName || "未选择"}</Tag>
            {focus ? (
              <>
                关注：<Tag>{focus}</Tag>
              </>
            ) : null}
          </Typography.Text>

          <AgentMessageList messages={session.messages} />
          <AgentIntentChips
            chips={session.chips}
            onSelect={session.sendChip}
            disabled={session.running}
          />
          <AgentChatInput onSend={session.sendMessage} loading={session.running} />

          {!hasGui && !session.running && (
            <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: 12 }}>
              发送意图后，采纳/确认等结构化操作将在结果抽屉中展示（GUI）。
            </Typography.Text>
          )}
        </Spin>
      </Card>

      <Drawer
        title={
          <Space>
            <span>Agent 结果与确认</span>
            {blockCount > 0 && <Tag>{blockCount} 项</Tag>}
          </Space>
        }
        placement="right"
        width={compact ? Math.min(520, window.innerWidth - 24) : 560}
        open={drawerOpen && hasGui}
        onClose={() => setDrawerOpen(false)}
        destroyOnClose={false}
        styles={{ body: { paddingTop: 12 } }}
      >
        <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginBottom: 12 }}>
          GUI — 根据会话结果动态渲染；高风险操作须在此完成确认。
        </Typography.Text>
        <UIBlockRenderer blocks={session.uiBlocks} session={guiSession} />
      </Drawer>
    </>
  );
}
