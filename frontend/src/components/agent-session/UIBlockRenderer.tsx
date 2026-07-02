import { useState } from "react";
import { App as AntApp, Button, Card, Input, List, Modal, Space, Statistic, Tag, Typography } from "antd";
import { Link } from "react-router-dom";
import type { UIBlock, UIAction, BearCase, WorkflowTodo } from "../../lib/api";
import { useUser } from "../../lib/userContext";
import { filterBlocksByOperator } from "../../lib/blockPermissions";
import type {
  SectorRecommendation,
  BottleneckRecommendation,
  Candidate,
  SerenityRecommendation,
  Sector,
} from "../../lib/api";
import AgentWorkflowProgress from "../AgentWorkflowProgress";
import type { SectorWorkflowStatus } from "../../lib/api";

export interface SessionHandlers {
  adoptSector: (recId: string, sectorName?: string) => Promise<void>;
  dismissSector: (recId: string) => Promise<void>;
  dismissBottleneck: (recId: string) => Promise<void>;
  confirmSerenity: (recId: string, reason: string) => Promise<void>;
  dismissSerenity: (recId: string) => Promise<void>;
  rebutBear: (bearId: string, rebuttal: string) => Promise<void>;
  runBlockAction: (actionId: string) => Promise<void>;
  handleTodoAction: (todo: WorkflowTodo) => Promise<void>;
  confirmSectorBeta: (sectorId: string, reason: string) => Promise<void>;
  navigate?: (path: string) => void;
}

interface BlockProps {
  block: UIBlock;
  session: SessionHandlers;
}

function BlockActionsBar({ block, session }: BlockProps) {
  const actions = block.actions || [];
  if (!actions.length) return null;
  return (
    <Space wrap style={{ marginTop: 8 }}>
      {actions.map((a: UIAction) => (
        <Button
          key={a.action_id}
          type={a.kind === "primary" ? "primary" : a.kind === "danger" ? "primary" : "default"}
          danger={a.kind === "danger"}
          size="small"
          onClick={() => {
            if (a.api_method === "navigate" && a.api_path) {
              session.navigate?.(a.api_path);
              return;
            }
            if (a.ontology_action === "ResumeOrchestrator" || a.action_id === "resume_orchestrator") {
              session.runBlockAction(a.action_id);
            }
          }}
        >
          {a.label}
        </Button>
      ))}
    </Space>
  );
}

function MetricCardsBlock({ block }: { block: UIBlock }) {
  const metrics = (block.data.metrics as { key: string; label: string; value: string }[]) || [];
  const disclaimer =
    typeof block.data.disclaimer === "string" ? block.data.disclaimer : undefined;
  return (
    <Card size="small" title={block.title} type="inner">
      <Space wrap>
        {metrics.map((m) => (
          <Statistic key={m.key} title={m.label} value={m.value} style={{ minWidth: 100 }} />
        ))}
      </Space>
      {disclaimer ? (
        <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 8 }}>
          {disclaimer}
        </Typography.Text>
      ) : null}
    </Card>
  );
}

function SectorRecEvidence({
  sector,
  rec,
}: {
  sector: Sector;
  rec?: SectorRecommendation;
}) {
  return (
    <Space direction="vertical" size={4} style={{ width: "100%" }}>
      <Space wrap size={4}>
        <Tag>需求增速 {sector.demand_growth_hint ?? rec?.demand_growth_hint ?? "—"}%</Tag>
        {rec && typeof rec.beta_score === "number" && (
          <Tag color="purple">beta {(rec.beta_score * 100).toFixed(0)}</Tag>
        )}
        {rec?.signals?.demand_growth_ok && <Tag color="green">需求达标</Tag>}
        {rec?.signals?.capex_positive && <Tag color="green">资本开支正向</Tag>}
        {typeof rec?.signals?.research_support_count === "number" && (
          <Tag color="blue">研报支撑 {rec.signals.research_support_count}</Tag>
        )}
      </Space>
      {rec?.terminal_products?.length ? (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          终端产品：{rec.terminal_products.slice(0, 5).join("、")}
        </Typography.Text>
      ) : null}
      {rec?.rationale ? (
        <Typography.Paragraph
          type="secondary"
          style={{ fontSize: 12, marginBottom: 0 }}
          ellipsis={{ rows: 3, tooltip: rec.rationale }}
        >
          推荐依据：{rec.rationale}
        </Typography.Paragraph>
      ) : (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          暂无智能体推荐证据，请结合产业看板 / 图谱自行研判后确认。
        </Typography.Text>
      )}
      {rec?.risks?.length ? (
        <Typography.Text type="warning" style={{ fontSize: 12 }}>
          风险：{rec.risks.slice(0, 3).join("；")}
        </Typography.Text>
      ) : null}
    </Space>
  );
}

function SectorPendingConfirmBlock({ block, session }: BlockProps) {
  const { message } = AntApp.useApp();
  const { can } = useUser();
  const items =
    (block.data.items as { sector: Sector; recommendation?: SectorRecommendation }[]) || [];
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const confirm = async (sector: Sector) => {
    const reason = (reasons[sector.id] || "").trim();
    if (reason.length < 5) {
      message.warning("请填写确认理由（≥5字），将写入审计留痕");
      return;
    }
    setLoadingId(sector.id);
    try {
      await session.confirmSectorBeta(sector.id, reason);
      setReasons((prev) => ({ ...prev, [sector.id]: "" }));
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <Card size="small" title={block.title} type="inner">
      <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
        在「待采纳赛道」中采纳推荐后，须在此填写理由确认景气，方可进入 Step 2。
      </Typography.Paragraph>
      <List
        size="small"
        dataSource={items}
        renderItem={({ sector, recommendation }) => (
          <List.Item>
            <Space direction="vertical" style={{ width: "100%" }} size={8}>
              <Space wrap>
                <Typography.Text strong>{sector.name}</Typography.Text>
                <Tag color="orange">待确认</Tag>
              </Space>
              <SectorRecEvidence sector={sector} rec={recommendation} />
              <Input.TextArea
                rows={2}
                placeholder="确认理由（≥5字，写入审计）"
                value={reasons[sector.id] || ""}
                onChange={(e) => setReasons((prev) => ({ ...prev, [sector.id]: e.target.value }))}
              />
              {can("confirm_sector_beta") ? (
                <Button type="primary" loading={loadingId === sector.id} onClick={() => confirm(sector)}>
                  确认赛道景气
                </Button>
              ) : (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  需研究员 / 基金经理权限
                </Typography.Text>
              )}
            </Space>
          </List.Item>
        )}
      />
    </Card>
  );
}

function SectorSettledListBlock({ block, session }: BlockProps) {
  const items = (block.data.items as Sector[]) || [];
  const isConfirmed = (s: Sector) => s.status === "beta_confirmed" && s.human_confirmed;

  return (
    <Card size="small" title={block.title} type="inner">
      <List
        size="small"
        dataSource={items}
        renderItem={(s) => (
          <List.Item
            actions={[
              <Link key="g" to="/graph">
                图谱
              </Link>,
              <Link key="d" to="/dashboard">
                看板
              </Link>,
              <Link key="c" to="/candidates">
                候选池
              </Link>,
            ]}
          >
            <Space direction="vertical" size={2}>
              <Space wrap>
                <Typography.Text strong>{s.name}</Typography.Text>
                {isConfirmed(s) ? (
                  <Tag color="green">已确认景气</Tag>
                ) : (
                  <Tag color="red">已驳回</Tag>
                )}
              </Space>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                需求增速提示：{s.demand_growth_hint ?? "—"}%
                {isConfirmed(s) ? " · 可继续 Step 2 知识构建" : " · 不进入后续流程"}
              </Typography.Text>
            </Space>
          </List.Item>
        )}
      />
    </Card>
  );
}

function SectorRecListBlock({ block, session }: BlockProps) {
  const { can } = useUser();
  const items = (block.data.items as SectorRecommendation[]) || [];
  return (
    <Card size="small" title={block.title} type="inner">
      <List
        size="small"
        dataSource={items}
        renderItem={(rec, idx) => (
          <List.Item
            actions={[
              can("adopt_sector") ? (
                <Button
                  key="a"
                  type="link"
                  size="small"
                  onClick={() => session.adoptSector(rec.rec_id, rec.sector_name)}
                >
                  采纳
                </Button>
              ) : (
                <Typography.Text key="a" type="secondary" style={{ fontSize: 12 }}>
                  需基金经理
                </Typography.Text>
              ),
              can("dismiss_proposal") ? (
                <Button key="d" type="link" size="small" onClick={() => session.dismissSector(rec.rec_id)}>
                  驳回
                </Button>
              ) : null,
            ].filter(Boolean)}
          >
            <Space direction="vertical" size={0}>
              <Space wrap>
                <Typography.Text type="secondary">#{idx + 1}</Typography.Text>
                <Typography.Text strong>{rec.sector_name}</Typography.Text>
                {typeof rec.beta_score === "number" && (
                  <Tag color="geekblue">景气 {(rec.beta_score * 100).toFixed(0)}</Tag>
                )}
                {rec.signals?.capex_positive && <Tag color="green">主力资金正向</Tag>}
                {typeof rec.signals?.research_support_count === "number" &&
                  rec.signals.research_support_count > 0 && (
                    <Tag color="blue">研报支撑 {rec.signals.research_support_count}</Tag>
                  )}
              </Space>
              <Typography.Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                {rec.rationale}
              </Typography.Text>
            </Space>
          </List.Item>
        )}
      />
    </Card>
  );
}

function PipelineStepsBlock({ block }: { block: UIBlock }) {
  const steps = (block.data.steps as { step: string; status: string; reason?: string }[]) || [];
  return (
    <Card size="small" title={block.title} type="inner">
      <List
        size="small"
        dataSource={steps}
        renderItem={(s) => (
          <List.Item>
            <Tag color={s.status === "ok" ? "green" : s.status === "skipped" ? "orange" : "red"}>
              {s.status}
            </Tag>
            {s.step}
            {s.reason && (
              <Typography.Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                {s.reason}
              </Typography.Text>
            )}
          </List.Item>
        )}
      />
    </Card>
  );
}

function WorkflowProgressBlock({ block, session }: BlockProps) {
  const ws = block.data as unknown as SectorWorkflowStatus;
  if (!ws.steps) return null;
  return (
    <Card size="small" title={block.title} type="inner">
      <AgentWorkflowProgress
        phases={ws.phases}
        currentPhase={ws.current_phase}
        steps={ws.steps}
        currentStep={ws.current_step}
        compact
      />
      {ws.graph_stats && (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          图谱：{ws.graph_stats.products} 产品 · {ws.graph_stats.companies} 成分股 · {ws.graph_stats.drafts}{" "}
          待校准草案
        </Typography.Text>
      )}
      <BlockActionsBar block={block} session={session} />
    </Card>
  );
}

function BottleneckRecBlock({ block, session }: BlockProps) {
  const items = (block.data.items as BottleneckRecommendation[]) || [];
  return (
    <Card size="small" title={block.title} type="inner">
      <List
        size="small"
        dataSource={items}
        renderItem={(rec) => (
          <List.Item
            actions={[
              <Link key="g" to="/graph">
                图谱
              </Link>,
              <Button key="d" type="link" size="small" onClick={() => session.dismissBottleneck(rec.rec_id)}>
                驳回
              </Button>,
            ]}
          >
            {rec.product_name} — {rec.hint_level} ({rec.hint_score})
          </List.Item>
        )}
      />
    </Card>
  );
}

function CandidateTableBlock({ block, session }: BlockProps) {
  const items = (block.data.items as Candidate[]) || [];
  const sectorId = block.data.sector_id as string;
  return (
    <Card size="small" title={block.title} type="inner" extra={<Link to={`/candidates?sector=${sectorId}`}>去候选池</Link>}>
      <List
        size="small"
        dataSource={items.slice(0, 10)}
        renderItem={(c) => (
          <List.Item>
            <Space wrap>
              <Typography.Text strong>{c.stock_code}</Typography.Text>
              {c.name}
              <Tag>分 {c.hint_score}</Tag>
              {c.priority === "P0" && <Tag color="magenta">P0</Tag>}
              {c.tag && <Tag color="orange">{c.tag}</Tag>}
              {c.status === "proposed" && <Tag color="blue">待确认</Tag>}
            </Space>
          </List.Item>
        )}
      />
      <BlockActionsBar block={block} session={session} />
    </Card>
  );
}

function KnowledgeDraftBlock({ block, session }: BlockProps) {
  const draftId = block.data.draft_id as string;
  const extracted = block.data.extracted as { relations?: { subject?: string; predicate?: string; object?: string }[] } | undefined;
  const relations = extracted?.relations || [];
  return (
    <Card size="small" title={block.title} type="inner">
      <Typography.Paragraph>
        草案 <Tag>{draftId}</Tag>
      </Typography.Paragraph>
      {relations.length > 0 && (
        <List
          size="small"
          header={`抽取关系预览（${relations.length} 条）`}
          dataSource={relations.slice(0, 5)}
          renderItem={(r) => (
            <List.Item style={{ fontSize: 12 }}>
              {r.subject} → {r.predicate} → {r.object}
            </List.Item>
          )}
        />
      )}
      <BlockActionsBar block={block} session={session} />
    </Card>
  );
}

function SerenityRecBlock({ block, session }: BlockProps) {
  const { message } = AntApp.useApp();
  const { can } = useUser();
  const items = (block.data.items as SerenityRecommendation[]) || [];
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);

  const doConfirm = async (recId: string) => {
    if (reason.trim().length < 5) {
      message.warning("请填写确认理由（≥5字）");
      return;
    }
    await session.confirmSerenity(recId, reason);
    setConfirming(null);
    setReason("");
  };

  return (
    <Card size="small" title={block.title} type="inner">
      <List
        size="small"
        dataSource={items}
        renderItem={(rec) => (
          <List.Item
            actions={[
              can("confirm_serenity") ? (
                <Button key="c" type="link" size="small" onClick={() => setConfirming(rec.rec_id)}>
                  确认
                </Button>
              ) : null,
              can("dismiss_proposal") ? (
                <Button key="d" type="link" size="small" onClick={() => session.dismissSerenity(rec.rec_id)}>
                  驳回
                </Button>
              ) : null,
            ].filter(Boolean)}
          >
            {rec.niche_product_name} — {rec.hop_count} 跳
          </List.Item>
        )}
      />
      <Modal
        title="确认 Serenity 路径"
        open={!!confirming}
        onOk={() => confirming && doConfirm(confirming)}
        onCancel={() => setConfirming(null)}
      >
        <Input.TextArea
          rows={3}
          placeholder="确认理由（≥5字）"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </Modal>
    </Card>
  );
}

function ReportDraftSummaryBlock({ block, session }: BlockProps) {
  const reportId = block.data.report_id as string;
  const report = block.data.report as {
    status?: string;
    logic_chain_steps?: number;
    citation_count?: number;
    counter_argument_count?: number;
    unverified_count?: number;
  };
  return (
    <Card size="small" title={block.title} type="inner">
      <Space wrap>
        <Tag color={report.status === "published" ? "green" : "orange"}>{report.status || "draft"}</Tag>
        {typeof report.logic_chain_steps === "number" && <Tag>{report.logic_chain_steps} 步逻辑链</Tag>}
        {typeof report.citation_count === "number" && <Tag>{report.citation_count} 条引用</Tag>}
        {typeof report.counter_argument_count === "number" && <Tag>{report.counter_argument_count} 项反证</Tag>}
        {typeof report.unverified_count === "number" && report.unverified_count > 0 && (
          <Tag color="red">{report.unverified_count} 条待核实</Tag>
        )}
      </Space>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
        报告号 {reportId} — 发布须人工审核
      </Typography.Paragraph>
      <BlockActionsBar block={block} session={session} />
    </Card>
  );
}

function BearCaseListBlock({ block, session }: BlockProps) {
  const { message } = AntApp.useApp();
  const { can } = useUser();
  const items = (block.data.items as BearCase[]) || [];
  const [rebutting, setRebutting] = useState<string | null>(null);
  const [rebuttal, setRebuttal] = useState("");

  const sevColor = (s: string) =>
    s === "高" || s === "high" ? "red" : s === "中" || s === "medium" ? "orange" : "green";

  const doRebut = async (bearId: string) => {
    if (rebuttal.trim().length < 5) {
      message.warning("回应须 ≥5 字");
      return;
    }
    await session.rebutBear(bearId, rebuttal);
    setRebutting(null);
    setRebuttal("");
  };

  return (
    <Card size="small" title={block.title} type="inner">
      <List
        size="small"
        dataSource={items}
        renderItem={(b) => (
          <List.Item
            actions={
              b.rebuttal_status === "rebutted"
                ? [<Tag key="ok" color="green">已回应</Tag>]
                : can("rebut_bear")
                  ? [
                      <Button key="r" type="link" size="small" danger onClick={() => setRebutting(b.bear_id)}>
                        回应
                      </Button>,
                    ]
                  : [<Typography.Text key="x" type="secondary" style={{ fontSize: 12 }}>需风控/基金经理</Typography.Text>]
            }
          >
            <Space direction="vertical" size={2}>
              <Space wrap>
                <Tag color="volcano">{b.stock_code}</Tag>
                <Tag>{b.dimension}</Tag>
                <Tag color={sevColor(b.severity)}>{b.severity}</Tag>
                <span>{b.risk}</span>
              </Space>
              {b.rebuttal && <Typography.Text type="success" style={{ fontSize: 12 }}>回应：{b.rebuttal}</Typography.Text>}
            </Space>
          </List.Item>
        )}
      />
      <Modal
        title="回应看空论点"
        open={!!rebutting}
        onOk={() => rebutting && doRebut(rebutting)}
        onCancel={() => setRebutting(null)}
      >
        <Input.TextArea
          rows={3}
          placeholder="回应内容（≥5字，高 severity 未回应将阻断入池）"
          value={rebuttal}
          onChange={(e) => setRebuttal(e.target.value)}
        />
      </Modal>
    </Card>
  );
}

function AlertFeedBlock({ block, session }: BlockProps) {
  const items = (block.data.items as Record<string, unknown>[]) || [];
  return (
    <Card size="small" title={block.title} type="inner">
      <List
        size="small"
        dataSource={items}
        renderItem={(item) => {
          const kind = item.kind as string | undefined;
          if (kind === "todo") {
            const todo = item as unknown as WorkflowTodo & { kind: string };
            return (
              <List.Item
                actions={[
                  <Button key="go" type="link" size="small" onClick={() => session.handleTodoAction(todo)}>
                    去处理
                  </Button>,
                ]}
              >
                <Space>
                  <Tag color="orange">{todo.count}</Tag>
                  {todo.message}
                </Space>
              </List.Item>
            );
          }
          const level = String(item.level || "info");
          return (
            <List.Item>
              <Tag color={level === "high" ? "red" : level === "medium" ? "orange" : "blue"}>
                {String(item.type || "alert")}
              </Tag>
              {String(item.message || "")}
            </List.Item>
          );
        }}
      />
      <BlockActionsBar block={block} session={session} />
    </Card>
  );
}

export default function UIBlockRenderer({ blocks, session }: { blocks: UIBlock[]; session: SessionHandlers }) {
  const { operator } = useUser();
  const visible = filterBlocksByOperator(blocks, operator);

  if (!visible.length) {
    return (
      <Typography.Text type="secondary">Agent 运行后，结构化结果将在此展示（GUI）</Typography.Text>
    );
  }
  return (
    <Space direction="vertical" style={{ width: "100%" }} size="middle">
      {visible.map((block) => {
        switch (block.type) {
          case "metric_cards":
            return <MetricCardsBlock key={block.block_id} block={block} />;
          case "sector_recommendation_list":
            return <SectorRecListBlock key={block.block_id} block={block} session={session} />;
          case "sector_pending_confirm_list":
            return <SectorPendingConfirmBlock key={block.block_id} block={block} session={session} />;
          case "sector_settled_list":
            return <SectorSettledListBlock key={block.block_id} block={block} session={session} />;
          case "pipeline_steps":
            return <PipelineStepsBlock key={block.block_id} block={block} />;
          case "workflow_progress":
            return <WorkflowProgressBlock key={block.block_id} block={block} session={session} />;
          case "bottleneck_rec_list":
            return <BottleneckRecBlock key={block.block_id} block={block} session={session} />;
          case "candidate_fusion_table":
            return <CandidateTableBlock key={block.block_id} block={block} session={session} />;
          case "knowledge_draft_preview":
            return <KnowledgeDraftBlock key={block.block_id} block={block} session={session} />;
          case "serenity_rec_list":
            return <SerenityRecBlock key={block.block_id} block={block} session={session} />;
          case "report_draft_summary":
            return <ReportDraftSummaryBlock key={block.block_id} block={block} session={session} />;
          case "bear_case_list":
            return <BearCaseListBlock key={block.block_id} block={block} session={session} />;
          case "alert_feed":
            return <AlertFeedBlock key={block.block_id} block={block} session={session} />;
          default:
            return (
              <Card key={block.block_id} size="small" title={block.title} type="inner">
                <Typography.Text type="secondary">未注册 Block 类型: {block.type}</Typography.Text>
              </Card>
            );
        }
      })}
    </Space>
  );
}
