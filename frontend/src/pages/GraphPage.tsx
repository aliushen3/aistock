import { useEffect, useRef, useState } from "react";
import { App as AntApp, Alert, Button, Card, Input, List, Modal, Select, Space, Spin, Tag, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import G6 from "@antv/g6";
import WorkflowEmptyGuide from "../components/WorkflowEmptyGuide";
import AgentPageStrip from "../components/agent-session/AgentPageStrip";
import { useUser } from "../lib/userContext";
import {
  confirmBottleneckRecommendation,
  confirmSerenityRecommendation,
  dismissBottleneckRecommendation,
  dismissSerenityRecommendation,
  getBottleneckRecommendations,
  getSectorGraph,
  getSectorWorkflowStatus,
  getSerenityRecommendations,
  getSerenityTrace,
  runBottleneckScoutAgent,
  runSerenityPathAgent,
  type BottleneckRecommendation,
  type GraphNode,
  type SerenityPath,
  type SerenityRecommendation,
} from "../lib/api";
import { useSector } from "../lib/sectorContext";

const PRODUCT_COLOR = (n: GraphNode, highlighted: Set<string>) => {
  if (highlighted.has(n.id)) return "#eb2f96";
  if (n.bottleneck_status === "bottleneck_confirmed") return "#cf1322";
  if (n.serenity_niche) return "#722ed1";
  if (n.bottleneck_status === "bottleneck_hint") return "#fa8c16";
  return "#1677ff";
};

export default function GraphPage() {
  const { message } = AntApp.useApp();
  const navigate = useNavigate();
  const { operator } = useUser();
  const { sectorId, setSectorId, sectors } = useSector();
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [loading, setLoading] = useState(true);
  const [nodeCount, setNodeCount] = useState(0);
  const [paths, setPaths] = useState<SerenityPath[]>([]);
  const [highlightIds, setHighlightIds] = useState<Set<string>>(new Set());
  const [traceLoading, setTraceLoading] = useState(false);
  const [agentLoading, setAgentLoading] = useState<string | null>(null);
  const [bottleneckRecs, setBottleneckRecs] = useState<BottleneckRecommendation[]>([]);
  const [serenityRecs, setSerenityRecs] = useState<SerenityRecommendation[]>([]);
  const [gated, setGated] = useState(false);
  const [gateMsg, setGateMsg] = useState<string | null>(null);
  const [stats, setStats] = useState<{ products: number; companies: number; drafts: number }>();

  const loadRecs = () => {
    if (!sectorId) return;
    getBottleneckRecommendations(sectorId, "proposed").then(setBottleneckRecs);
    getSerenityRecommendations(sectorId, "proposed").then(setSerenityRecs);
    getSectorWorkflowStatus(sectorId).then((ws) => {
      setStats(ws.graph_stats);
      if (!ws.sector_confirmed) {
        setGated(true);
        setGateMsg("赛道尚未确认景气，瓶颈/Serenity 确认需在 Step 1 完成后进行");
      } else {
        setGated(false);
        setGateMsg(null);
      }
    });
  };

  const renderGraph = (g: Awaited<ReturnType<typeof getSectorGraph>>, highlight: Set<string>) => {
    if (!containerRef.current) return;
    setNodeCount(g.nodes.length);
    const nodes = g.nodes.map((n) => {
      const isStale = n.type === "product" && n.freshness === "stale";
      return {
        id: n.id,
        label:
          n.type === "product"
            ? `${n.label}\n${n.hint_score ?? ""}${isStale ? " ⚠过期" : ""}`
            : n.label,
        nodeType: n.type,
        type: n.type === "company" ? "rect" : "circle",
        size: n.type === "company" ? [110, 32] : 48,
        style: {
          fill: n.type === "company" ? "#f6ffed" : PRODUCT_COLOR(n, highlight),
          opacity: isStale ? 0.55 : 1,
          stroke: highlight.has(n.id)
            ? "#eb2f96"
            : isStale
            ? "#8c8c8c"
            : n.type === "company"
            ? "#52c41a"
            : "#fff",
          lineWidth: highlight.has(n.id) ? 4 : isStale ? 3 : 2,
          lineDash: isStale ? [3, 3] : undefined,
        },
        labelCfg: { style: { fill: n.type === "company" ? "#135200" : "#fff", fontSize: 11 } },
      };
    });
    const edges = g.edges.map((e) => ({
      source: e.source,
      target: e.target,
      style: {
        stroke: highlight.has(e.source) && highlight.has(e.target) ? "#eb2f96" : e.type === "PRODUCES" ? "#b7eb8f" : "#bfbfbf",
        lineWidth: highlight.has(e.source) && highlight.has(e.target) ? 3 : 1,
        lineDash: e.type === "PRODUCES" ? [4, 4] : undefined,
        endArrow: true,
      },
    }));

    const width = containerRef.current.scrollWidth || 1000;
    if (graphRef.current) graphRef.current.destroy();
    const graph = new G6.Graph({
      container: containerRef.current,
      width,
      height: 560,
      layout: { type: "dagre", rankdir: "LR", nodesep: 18, ranksep: 70 },
      defaultNode: { type: "circle" },
      modes: { default: ["drag-canvas", "zoom-canvas", "drag-node"] },
      fitView: true,
      fitViewPadding: 20,
    });
    graph.data({ nodes, edges });
    graph.render();
    graph.on("node:click", (evt: { item: { getModel: () => { id: string; nodeType?: string } } }) => {
      const model = evt.item.getModel();
      if (model.nodeType === "product") navigate(`/products/${model.id}`);
    });
    graphRef.current = graph;
  };

  useEffect(() => {
    if (!sectorId || !containerRef.current) return;
    setLoading(true);
    getSectorGraph(sectorId)
      .then((g) => renderGraph(g, highlightIds))
      .finally(() => setLoading(false));
    loadRecs();
    return () => {
      if (graphRef.current) {
        graphRef.current.destroy();
        graphRef.current = null;
      }
    };
  }, [sectorId, highlightIds, navigate]);

  const runSerenityTrace = () => {
    setTraceLoading(true);
    getSerenityTrace(sectorId)
      .then((r) => {
        setPaths(r.paths);
        if (r.paths.length) {
          setHighlightIds(new Set(r.paths[0].node_ids));
        }
      })
      .finally(() => setTraceLoading(false));
  };

  const runAgent = async (key: string, fn: () => Promise<unknown>) => {
    setAgentLoading(key);
    try {
      await fn();
      message.success("Agent 运行完成");
      loadRecs();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "运行失败");
    } finally {
      setAgentLoading(null);
    }
  };

  const highlightPath = (p: SerenityPath) => setHighlightIds(new Set(p.node_ids));

  const confirmBottleneck = (rec: BottleneckRecommendation) => {
    let reason = "";
    Modal.confirm({
      title: `确认瓶颈 — ${rec.product_name}`,
      content: (
        <div>
          <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
            {rec.rationale}（提示分 {rec.hint_score} · {rec.hint_level}）
          </Typography.Paragraph>
          <Input.TextArea
            rows={3}
            placeholder="确认理由（≥5 字），高风险操作将进入双人复核"
            onChange={(e) => (reason = e.target.value)}
          />
        </div>
      ),
      onOk: async () => {
        if (reason.trim().length < 5) {
          message.error("理由至少 5 个字");
          throw new Error("reason too short");
        }
        try {
          const r = await confirmBottleneckRecommendation(rec.rec_id, reason, operator);
          message.success(r.message ?? "已提交瓶颈确认");
          loadRecs();
        } catch (e: unknown) {
          const err = e as { response?: { data?: { detail?: string } } };
          message.error(err.response?.data?.detail ?? "确认失败");
          throw e;
        }
      },
    });
  };

  const confirmSerenity = (rec: SerenityRecommendation) => {
    let reason = "";
    Modal.confirm({
      title: `确认 Serenity 小众环节 — ${rec.niche_product_name}`,
      content: (
        <Input.TextArea
          rows={3}
          placeholder="确认理由（替代难度/不可替代性等定性判断须人工确认）"
          onChange={(e) => (reason = e.target.value)}
        />
      ),
      onOk: async () => {
        if (reason.trim().length < 5) {
          message.error("理由至少 5 个字");
          throw new Error("reason too short");
        }
        await confirmSerenityRecommendation(rec.rec_id, reason);
        message.success("已确认 Serenity 路径");
        loadRecs();
      },
    });
  };

  const isEmpty = !loading && nodeCount === 0;

  return (
    <Card
      title="产业研究（阶段③ 环节挖掘 — 瓶颈 / Serenity 双视角）"
      extra={
        <Space wrap>
          <Button
            loading={agentLoading === "bottleneck"}
            onClick={() => runAgent("bottleneck", () => runBottleneckScoutAgent({ sector_id: sectorId }))}
          >
            瓶颈扫描 Agent
          </Button>
          <Button
            loading={agentLoading === "serenity"}
            onClick={() => runAgent("serenity", () => runSerenityPathAgent({ sector_id: sectorId }))}
          >
            Serenity 溯源 Agent
          </Button>
          <Button loading={traceLoading} onClick={runSerenityTrace}>
            一键逆向溯源
          </Button>
          <Button onClick={() => setHighlightIds(new Set())}>清除高亮</Button>
          <Select
            value={sectorId}
            style={{ width: 160 }}
            options={sectors.map((s) => ({ value: s.id, label: s.name }))}
            onChange={setSectorId}
          />
        </Space>
      }
    >
      {gated && gateMsg && (
        <Alert type="warning" showIcon message={gateMsg} style={{ marginBottom: 12 }} />
      )}
      <Space style={{ marginBottom: 12 }} wrap>
        <Typography.Text type="secondary">图例：</Typography.Text>
        <Tag color="#cf1322">已确认瓶颈</Tag>
        <Tag color="#fa8c16">疑似瓶颈</Tag>
        <Tag color="#722ed1">Serenity 小众</Tag>
        <Tag color="#52c41a">上市公司</Tag>
      </Space>
      {isEmpty ? (
        <WorkflowEmptyGuide
          step={3}
          sectorId={sectorId}
          stats={stats}
          gated={gated}
          gateMessage={gateMsg ?? undefined}
          onSyncConstituents={loadRecs}
        />
      ) : (
        <Spin spinning={loading}>
          <div ref={containerRef} style={{ width: "100%", height: 560, border: "1px solid #f0f0f0" }} />
        </Spin>
      )}
      {(bottleneckRecs.length > 0 || serenityRecs.length > 0) && (
        <Card size="small" title="待确认提案" style={{ marginTop: 12 }}>
          {bottleneckRecs.length > 0 && (
            <List
              size="small"
              header="瓶颈提案"
              dataSource={bottleneckRecs}
              renderItem={(rec) => (
                <List.Item
                  actions={[
                    <Button
                      key="c"
                      size="small"
                      type="primary"
                      disabled={gated}
                      onClick={() => confirmBottleneck(rec)}
                    >
                      确认瓶颈
                    </Button>,
                    <Button
                      key="d"
                      size="small"
                      onClick={() => dismissBottleneckRecommendation(rec.rec_id).then(loadRecs)}
                    >
                      驳回
                    </Button>,
                  ]}
                >
                  <Space size={4} wrap>
                    <Typography.Text strong>{rec.product_name}</Typography.Text>
                    <Tag color={rec.hint_level === "hint_high" ? "red" : "orange"}>{rec.hint_level}</Tag>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      提示分 {rec.hint_score} · {rec.rationale}
                    </Typography.Text>
                  </Space>
                </List.Item>
              )}
            />
          )}
          {serenityRecs.length > 0 && (
            <List
              size="small"
              header="Serenity 路径"
              dataSource={serenityRecs}
              renderItem={(rec) => (
                <List.Item
                  actions={[
                    <Button
                      key="c"
                      size="small"
                      type="primary"
                      disabled={gated}
                      onClick={() => confirmSerenity(rec)}
                    >
                      确认小众
                    </Button>,
                    <Button
                      key="d"
                      size="small"
                      onClick={() => dismissSerenityRecommendation(rec.rec_id).then(loadRecs)}
                    >
                      驳回
                    </Button>,
                  ]}
                >
                  <Space size={4} wrap>
                    <Typography.Text strong>{rec.niche_product_name}</Typography.Text>
                    <Tag color="purple">{rec.hop_count} 跳</Tag>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {rec.rationale}
                    </Typography.Text>
                  </Space>
                </List.Item>
              )}
            />
          )}
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            确认瓶颈为高风险操作（双人复核）；确认/驳回将写入审计日志
          </Typography.Text>
        </Card>
      )}
      {paths.length > 0 && (
        <Card size="small" title="Serenity 逆向溯源路径" style={{ marginTop: 12 }}>
          <List
            size="small"
            dataSource={paths.slice(0, 5)}
            renderItem={(p) => (
              <List.Item actions={[<a key="hl" onClick={() => highlightPath(p)}>高亮</a>]}>
                <Tag color="purple">{p.niche_product_name}</Tag>
                {p.hop_count} 跳 · {p.node_names.join(" → ")}
              </List.Item>
            )}
          />
        </Card>
      )}
      <div style={{ marginTop: 16 }}>
        <AgentPageStrip
          sectorId={sectorId}
          focus="graph"
          workflowStep={3}
          pageHint="本页 Agent：瓶颈扫描、Serenity 溯源、逆向溯源"
          onReload={loadRecs}
        />
      </div>
    </Card>
  );
}
