import { useEffect, useMemo, useState } from "react";
import {
  App as AntApp,
  Alert,
  Button,
  Card,
  Empty,
  Input,
  List,
  Space,
  Tabs,
  Tag,
  Typography,
} from "antd";
import {
  adoptSectorRecommendation,
  confirmSerenityRecommendation,
  dismissBottleneckRecommendation,
  dismissSectorRecommendation,
  dismissSerenityRecommendation,
  getBottleneckRecommendations,
  getSectorRecommendations,
  getSerenityRecommendations,
  runBottleneckScoutAgent,
  runCandidateFusionAgent,
  runKnowledgeIngestAgent,
  runMonitorWatchAgent,
  runOrchestrator,
  runReportGraphRAGAgent,
  runSectorRecommendAgent,
  runSerenityPathAgent,
  type AgentRunSummary,
  type BottleneckRecommendation,
  type SectorRecommendation,
  type SerenityRecommendation,
} from "../lib/api";

interface Props {
  sectorId: string;
  sectorName?: string;
  focus: string;
  query: string;
  onFocusChange?: (focus: string) => void;
  onReload?: () => void;
}

function SectorRecommendationList({
  items,
  onAdopt,
  onDismiss,
}: {
  items: SectorRecommendation[];
  onAdopt: (rec: SectorRecommendation) => void;
  onDismiss: (recId: string) => void;
}) {
  if (items.length === 0) {
    return null;
  }
  return (
    <List
      size="small"
      bordered
      header={
        <Space>
          <Typography.Text strong>待采纳赛道（按景气分排序）</Typography.Text>
          <Tag color="blue">{items.length} 条</Tag>
        </Space>
      }
      dataSource={items}
      renderItem={(rec, idx) => (
        <List.Item
          actions={[
            <Button key="a" type="primary" size="small" onClick={() => onAdopt(rec)}>
              采纳
            </Button>,
            <Button key="d" size="small" onClick={() => onDismiss(rec.rec_id)}>
              驳回
            </Button>,
          ]}
        >
          <List.Item.Meta
            title={
              <Space wrap>
                <Typography.Text type="secondary">#{idx + 1}</Typography.Text>
                <Typography.Text strong>{rec.sector_name}</Typography.Text>
                {typeof rec.beta_score === "number" && (
                  <Tag color="geekblue">景气分 {(rec.beta_score * 100).toFixed(0)}</Tag>
                )}
                {rec.signals?.capex_positive && <Tag color="green">主力资金正向</Tag>}
                {typeof rec.signals?.research_support_count === "number" &&
                  rec.signals.research_support_count > 0 && (
                    <Tag color="blue">题材/研报支撑 {rec.signals.research_support_count}</Tag>
                  )}
              </Space>
            }
            description={rec.rationale}
          />
        </List.Item>
      )}
    />
  );
}

export default function AgentConsole({ sectorId, sectorName, focus, query, onFocusChange, onReload }: Props) {
  const { message } = AntApp.useApp();
  const [loadingKey, setLoadingKey] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<AgentRunSummary | null>(null);
  const [sectorRecs, setSectorRecs] = useState<SectorRecommendation[]>([]);
  const [bottleneckRecs, setBottleneckRecs] = useState<BottleneckRecommendation[]>([]);
  const [serenityRecs, setSerenityRecs] = useState<SerenityRecommendation[]>([]);
  const [knowledgeContent, setKnowledgeContent] = useState(
    "磷化铟衬底是 EML光芯片 的上游，产能紧张扩产周期长达24个月，属于瓶颈环节。"
  );
  const [serenityReason, setSerenityReason] = useState("");

  const loadProposals = () => {
    Promise.all([
      getSectorRecommendations("proposed"),
      getBottleneckRecommendations(sectorId, "proposed"),
      getSerenityRecommendations(sectorId, "proposed"),
    ]).then(([s, b, ser]) => {
      setSectorRecs(s);
      setBottleneckRecs(b);
      setSerenityRecs(ser);
    });
  };

  useEffect(() => {
    loadProposals();
  }, [sectorId]);

  const displaySectorRecs = useMemo(() => {
    if (sectorRecs.length > 0) {
      return sectorRecs;
    }
    const fromRun = (lastResult as { recommendations?: SectorRecommendation[] } | null)?.recommendations;
    return fromRun?.length ? fromRun : [];
  }, [sectorRecs, lastResult]);

  const handleAdopt = async (rec: SectorRecommendation) => {
    try {
      const r = await adoptSectorRecommendation(rec.rec_id);
      loadProposals();
      onReload?.();
      const boot = r.bootstrap as {
        constituents?: { status?: string; reason?: string };
        report_draft?: { status?: string; draft_id?: string };
      } | null;
      if (!boot) {
        message.success(`已采纳赛道「${rec.sector_name}」`);
        return;
      }
      if (boot.constituents?.status === "skipped") {
        message.warning(`已采纳「${rec.sector_name}」；成分股同步跳过：${boot.constituents.reason ?? "未配置"}`);
      } else {
        message.success(`已采纳「${rec.sector_name}」并触发赛道冷启动`);
      }
      if (boot.report_draft?.draft_id) {
        message.info(`已生成知识草案 ${boot.report_draft.draft_id}`);
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || "采纳失败");
    }
  };

  const run = async (key: string, fn: () => Promise<AgentRunSummary | Record<string, unknown>>) => {
    setLoadingKey(key);
    try {
      const result = (await fn()) as AgentRunSummary & { recommendations?: SectorRecommendation[] };
      setLastResult(result);
      if (result.recommendations?.length) {
        setSectorRecs(result.recommendations);
        message.success(`扫描完成，发现 ${result.recommendations.length} 条待采纳推荐`);
      } else {
        message.warning(result.agent_summary || "扫描完成，但未产生可采纳推荐");
      }
      loadProposals();
      onReload?.();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || "智能体运行失败");
    } finally {
      setLoadingKey(null);
    }
  };

  const runColdStartScan = () => {
    onFocusChange?.("");
    run("sector-cold", () =>
      runSectorRecommendAgent({ query: query || undefined, max_recommendations: 5, force_cold_start: true })
    );
  };

  return (
    <Card title="赛道发现与研判工具" style={{ marginBottom: 16 }}>
      <Tabs
        items={[
          {
            key: "sector",
            label: "赛道推荐",
            children: (
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                <Alert
                  type="info"
                  showIcon
                  message="怎么用"
                  description={
                    <>
                      <strong>发现景气赛道</strong>：不限方向，按主力资金 + 多日涨幅 + 同花顺题材热度综合排序，最快看到当前最景气的板块。
                      <br />
                      <strong>按关注方向扫描</strong>：结合你填写的「{focus || "观察焦点"}」与已上传研报，生成更贴合的候选。
                      <br />
                      两种方式产出的推荐都在下方列表，点 <strong>采纳</strong> 即建立赛道。
                    </>
                  }
                />
                <Space wrap>
                  <Button
                    type="primary"
                    loading={loadingKey === "sector-cold"}
                    onClick={runColdStartScan}
                  >
                    发现景气赛道
                  </Button>
                  <Button
                    loading={loadingKey === "sector"}
                    onClick={() =>
                      run("sector", () =>
                        runSectorRecommendAgent({ focus: focus || undefined, query: query || undefined })
                      )
                    }
                  >
                    {focus ? `按关注方向「${focus}」扫描` : "按关注方向扫描"}
                  </Button>
                </Space>
                {displaySectorRecs.length > 0 ? (
                  <SectorRecommendationList
                    items={displaySectorRecs}
                    onAdopt={handleAdopt}
                    onDismiss={(recId) => dismissSectorRecommendation(recId).then(loadProposals)}
                  />
                ) : (
                  <Empty
                    description="暂无待采纳赛道。点击上方「发现景气赛道」开始，或上传研报后按方向扫描。"
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                )}
              </Space>
            ),
          },
          {
            key: "pipeline",
            label: "研判流水线",
            children: (
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                <Typography.Text>
                  当前赛道：<Tag color={sectorId ? "blue" : undefined}>{sectorName || (sectorId ? "已选择" : "未选择")}</Tag>
                  {!sectorId && (
                    <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                      请先在上方采纳并选择一个赛道
                    </Typography.Text>
                  )}
                </Typography.Text>
                <Input.TextArea
                  rows={3}
                  value={knowledgeContent}
                  onChange={(e) => setKnowledgeContent(e.target.value)}
                  placeholder="知识抽取内容（≥20字）"
                />
                <Space wrap>
                  <Button
                    loading={loadingKey === "knowledge"}
                    onClick={() =>
                      run("knowledge", () =>
                        runKnowledgeIngestAgent({
                          sector_id: sectorId,
                          source_ref: "Agent控制台",
                          content: knowledgeContent,
                        })
                      )
                    }
                  >
                    知识抽取
                  </Button>
                  <Button
                    loading={loadingKey === "bottleneck"}
                    onClick={() => run("bottleneck", () => runBottleneckScoutAgent({ sector_id: sectorId }))}
                  >
                    瓶颈扫描
                  </Button>
                  <Button
                    loading={loadingKey === "serenity"}
                    onClick={() => run("serenity", () => runSerenityPathAgent({ sector_id: sectorId }))}
                  >
                    受益溯源
                  </Button>
                  <Button
                    loading={loadingKey === "report"}
                    onClick={() =>
                      run("report", () => runReportGraphRAGAgent({ sector_id: sectorId, mode: "fusion" }))
                    }
                  >
                    生成报告初稿
                  </Button>
                  <Button
                    loading={loadingKey === "fusion"}
                    onClick={() =>
                      run("fusion", () => runCandidateFusionAgent({ sector_id: sectorId, mode: "fusion" }))
                    }
                  >
                    候选融合
                  </Button>
                  <Button
                    loading={loadingKey === "monitor"}
                    onClick={() => run("monitor", () => runMonitorWatchAgent({ sector_id: sectorId }))}
                  >
                    动态监控
                  </Button>
                </Space>
                {bottleneckRecs.length > 0 && (
                  <List
                    size="small"
                    header="待确认瓶颈环节（去「产业图谱」确认）"
                    dataSource={bottleneckRecs}
                    renderItem={(rec) => (
                      <List.Item
                        actions={[
                          <a key="d" onClick={() => dismissBottleneckRecommendation(rec.rec_id).then(loadProposals)}>
                            驳回
                          </a>,
                        ]}
                      >
                        {rec.product_name} — {rec.hint_level} ({rec.hint_score})
                      </List.Item>
                    )}
                  />
                )}
                {serenityRecs.length > 0 && (
                  <List
                    size="small"
                    header="待确认受益路径"
                    dataSource={serenityRecs}
                    renderItem={(rec) => (
                      <List.Item
                        actions={[
                          <a
                            key="c"
                            onClick={() => {
                              if (serenityReason.trim().length < 5) {
                                message.warning("请填写确认理由（≥5字）");
                                return;
                              }
                              confirmSerenityRecommendation(rec.rec_id, serenityReason).then(loadProposals);
                            }}
                          >
                            确认
                          </a>,
                          <a key="d" onClick={() => dismissSerenityRecommendation(rec.rec_id).then(loadProposals)}>
                            驳回
                          </a>,
                        ]}
                      >
                        {rec.niche_product_name} — {rec.hop_count} 跳
                      </List.Item>
                    )}
                  />
                )}
                <Input.TextArea
                  rows={2}
                  placeholder="Serenity 确认理由（≥5字）"
                  value={serenityReason}
                  onChange={(e) => setSerenityReason(e.target.value)}
                />
              </Space>
            ),
          },
          {
            key: "orchestrator",
            label: "一键全流程",
            children: (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Typography.Paragraph type="secondary">
                  自动串联「赛道发现 → 瓶颈扫描 → 受益溯源 → 报告初稿 → 候选融合 → 动态监控」六步；
                  未确认景气的赛道会自动跳过需门控的步骤，确保人工把关。
                </Typography.Paragraph>
                <Button
                  type="primary"
                  loading={loadingKey === "orchestrator"}
                  onClick={() =>
                    run("orchestrator", () =>
                      runOrchestrator({
                        sector_id: sectorId,
                        focus: focus || undefined,
                        query: query || undefined,
                        content: knowledgeContent,
                        mode: "fusion",
                        stop_on_gate: true,
                        steps: [
                          "sector_recommend",
                          "bottleneck_scout",
                          "serenity_path",
                          "report_graphrag",
                          "candidate_fusion",
                          "monitor_watch",
                        ],
                      })
                    )
                  }
                >
                  一键运行全流程
                </Button>
              </Space>
            ),
          },
        ]}
      />
      {lastResult && (
        <Alert
          style={{ marginTop: 16 }}
          type="info"
          showIcon
          message="运行结果"
          description={
            <>
              {lastResult.agent_summary && <div>{lastResult.agent_summary}</div>}
              {typeof lastResult.alert_count === "number" && (
                <div>告警 {lastResult.alert_count} 条</div>
              )}
              {typeof lastResult.candidate_count === "number" && (
                <div>候选 {lastResult.candidate_count} 个</div>
              )}
              {lastResult.disclaimer && (
                <Typography.Text type="secondary">{lastResult.disclaimer}</Typography.Text>
              )}
            </>
          }
        />
      )}
      {focus && (
        <Typography.Text type="secondary" style={{ display: "block", marginTop: 8 }}>
          观察焦点：{focus}
          {onFocusChange && (
            <>
              {" "}
              <Typography.Link onClick={() => onFocusChange("")}>清除</Typography.Link>
            </>
          )}
        </Typography.Text>
      )}
    </Card>
  );
}
