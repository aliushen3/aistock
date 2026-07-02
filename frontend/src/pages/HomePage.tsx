import { useEffect, useState } from "react";
import { Alert, App as AntApp, Typography } from "antd";
import AgentSessionPanel from "../components/agent-session/AgentSessionPanel";
import DecisionInbox from "../components/cockpit/DecisionInbox";
import SectorWorkflowBoard from "../components/cockpit/SectorWorkflowBoard";
import WatchlistPanel from "../components/WatchlistPanel";
import WorkflowGuide from "../components/WorkflowGuide";
import { useSector } from "../lib/sectorContext";
import {
  getAlerts,
  getGlobalAlerts,
  getSectorWorkflowStatus,
  getWorkflowOverview,
  runOrchestrator,
  type AlertItem,
  type SectorWorkflowOverviewItem,
  type SectorWorkflowStatus,
  type WatchlistItem,
} from "../lib/api";

export default function HomePage() {
  const { message } = AntApp.useApp();
  const { sectorId: activeSectorId, setSectorId: setActiveSectorId, reloadSectors, sectors } = useSector();
  const [overview, setOverview] = useState<SectorWorkflowOverviewItem[]>([]);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [globalAlerts, setGlobalAlerts] = useState<AlertItem[]>([]);
  const [sessionAlerts, setSessionAlerts] = useState<AlertItem[]>([]);
  const [workflow, setWorkflow] = useState<SectorWorkflowStatus | null>(null);
  const [agentFocus, setAgentFocus] = useState<string | undefined>(undefined);
  const [resumingId, setResumingId] = useState<string | null>(null);

  const load = () => {
    reloadSectors();
    setOverviewLoading(true);
    Promise.all([getWorkflowOverview(), getGlobalAlerts()])
      .then(([ov, ga]) => {
        setOverview(ov.items);
        setGlobalAlerts(ga.items);
      })
      .finally(() => setOverviewLoading(false));

    if (!activeSectorId) {
      setSessionAlerts([]);
      setWorkflow(null);
      return;
    }
    Promise.all([getAlerts(activeSectorId), getSectorWorkflowStatus(activeSectorId)]).then(
      ([sector, ws]) => {
        setSessionAlerts(sector.items);
        setWorkflow(ws);
      }
    );
  };

  useEffect(() => {
    load();
  }, [activeSectorId]);

  const handleResume = async (sectorId: string) => {
    setResumingId(sectorId);
    try {
      const r = await runOrchestrator({ sector_id: sectorId, resume: true, stop_on_gate: true });
      const summary = (r.agent_summary as string) || "编排器已推进，到人工门控点暂停";
      message.success(summary);
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "一键投研运行失败");
    } finally {
      setResumingId(null);
    }
  };

  const handleWatchlistSelect = (item: WatchlistItem) => {
    setAgentFocus(item.sector_name);
    if (item.sector_id) {
      setActiveSectorId(item.sector_id);
    }
  };

  const activeSectorName =
    workflow?.sector_name ?? sectors.find((s) => s.id === activeSectorId)?.name;
  const isEmpty = sectors.length === 0;

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 4 }}>
        投研驾驶舱
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        Agent 自动推进五阶段流程（赛道 → 产业链 → 环节 → 标的 → 跟踪），到人工门控点暂停并进入
        <Typography.Text strong>决策收件箱</Typography.Text>等你裁决。
        系统评分仅供排序，投研决策由你把关。
      </Typography.Paragraph>

      {isEmpty ? (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="从这里开始：发现第一个景气赛道"
            description={
              <>
                在下方 <strong>Agent 会话</strong> 输入「发现景气赛道」（可写明关注方向，如「发现景气赛道
                关注氟化工」）→ 在结果面板采纳推荐 → 确认景气，Agent 即可开始自动推进。
              </>
            }
          />
          <WorkflowGuide />
        </>
      ) : (
        <>
          <SectorWorkflowBoard
            items={overview}
            activeSectorId={activeSectorId}
            loading={overviewLoading}
            resumingId={resumingId}
            onSelect={setActiveSectorId}
            onResume={handleResume}
          />
          <DecisionInbox
            overview={overview}
            globalAlerts={globalAlerts}
            loading={overviewLoading}
            onSelectSector={setActiveSectorId}
          />
        </>
      )}

      <AgentSessionPanel
        sectorId={activeSectorId}
        sectorName={activeSectorName}
        focus={agentFocus}
        workflowStep={workflow?.current_step}
        workflowStatus={workflow}
        pendingTodos={workflow?.pending_todos}
        alerts={sessionAlerts}
        resumeSteps={workflow?.resume_steps}
        onReload={load}
      />

      <WatchlistPanel
        focus={agentFocus}
        selectedSectorId={activeSectorId}
        onSelect={handleWatchlistSelect}
      />
    </div>
  );
}
