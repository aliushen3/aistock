import { useEffect, useState } from "react";
import {
  App as AntApp,
  Alert,
  Button,
  Card,
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
  focus: string;
  query: string;
  onFocusChange?: (focus: string) => void;
  onReload?: () => void;
}

export default function AgentConsole({ sectorId, focus, query, onFocusChange, onReload }: Props) {
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

  const run = async (key: string, fn: () => Promise<AgentRunSummary | Record<string, unknown>>) => {
    setLoadingKey(key);
    try {
      const result = (await fn()) as AgentRunSummary;
      setLastResult(result);
      message.success(`${result.agent} 完成`);
      loadProposals();
      onReload?.();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || "智能体运行失败");
    } finally {
      setLoadingKey(null);
    }
  };

  return (
    <Card title="智能体控制台（7 Agent + Orchestrator）" style={{ marginBottom: 16 }}>
      <Tabs
        items={[
          {
            key: "sector",
            label: "赛道推荐",
            children: (
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                <Typography.Text type="secondary">
                  ReAct 扫描：指标 → 研报 → 动态观察清单 → Beta 提案
                </Typography.Text>
                <Button
                  type="primary"
                  loading={loadingKey === "sector"}
                  onClick={() =>
                    run("sector", () =>
                      runSectorRecommendAgent({ focus: focus || undefined, query: query || undefined })
                    )
                  }
                >
                  运行赛道扫描
                </Button>
                {sectorRecs.length > 0 && (
                  <List
                    size="small"
                    header="待采纳赛道推荐"
                    dataSource={sectorRecs}
                    renderItem={(rec) => (
                      <List.Item
                        actions={[
                          <a key="a" onClick={() => adoptSectorRecommendation(rec.rec_id).then(loadProposals)}>
                            采纳
                          </a>,
                          <a key="d" onClick={() => dismissSectorRecommendation(rec.rec_id).then(loadProposals)}>
                            驳回
                          </a>,
                        ]}
                      >
                        <List.Item.Meta
                          title={
                            <Space>
                              {rec.sector_name}
                              <Tag color="purple">{rec.agent_mode}</Tag>
                            </Space>
                          }
                          description={rec.rationale}
                        />
                      </List.Item>
                    )}
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
                  当前赛道：<Tag>{sectorId}</Tag>
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
                    Serenity 溯源
                  </Button>
                  <Button
                    loading={loadingKey === "report"}
                    onClick={() =>
                      run("report", () => runReportGraphRAGAgent({ sector_id: sectorId, mode: "fusion" }))
                    }
                  >
                    GraphRAG 报告
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
                    header="待确认瓶颈提案（→ 图谱页 ConfirmBottleneck）"
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
                    header="待确认 Serenity 路径"
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
            label: "七步编排",
            children: (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Typography.Paragraph type="secondary">
                  按门控串联七步 Agent；未确认赛道时 gated 步骤会跳过或中止（stop_on_gate=true）。
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
                  运行 Orchestrator（门控模式）
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
          message={
            <Space>
              <Tag>{lastResult.agent}</Tag>
              {lastResult.agent_mode && <Tag color="purple">{lastResult.agent_mode}</Tag>}
            </Space>
          }
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
