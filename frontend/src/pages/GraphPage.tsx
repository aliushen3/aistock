import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, List, Select, Space, Spin, Tag, Typography } from "antd";
import G6 from "@antv/g6";
import { getSectorGraph, getSectors, getSerenityTrace, type GraphNode, type SerenityPath } from "../lib/api";

const PRODUCT_COLOR = (n: GraphNode, highlighted: Set<string>) => {
  if (highlighted.has(n.id)) return "#eb2f96";
  if (n.bottleneck_status === "bottleneck_confirmed") return "#cf1322";
  if (n.serenity_niche) return "#722ed1";
  if (n.bottleneck_status === "bottleneck_hint") return "#fa8c16";
  return "#1677ff";
};

export default function GraphPage() {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [sectors, setSectors] = useState<{ id: string; name: string }[]>([]);
  const [sectorId, setSectorId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [paths, setPaths] = useState<SerenityPath[]>([]);
  const [highlightIds, setHighlightIds] = useState<Set<string>>(new Set());
  const [traceLoading, setTraceLoading] = useState(false);

  useEffect(() => {
    getSectors().then((s) => {
      setSectors(s);
      if (s.length) setSectorId(s[0].id);
    });
  }, []);

  const renderGraph = (g: Awaited<ReturnType<typeof getSectorGraph>>, highlight: Set<string>) => {
    if (!containerRef.current) return;
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
          const ids = new Set(r.paths[0].node_ids);
          setHighlightIds(ids);
        }
      })
      .finally(() => setTraceLoading(false));
  };

  const highlightPath = (p: SerenityPath) => setHighlightIds(new Set(p.node_ids));

  return (
    <Card
      title="产业链拓扑（沿 UPSTREAM_OF 自上游 → 终端）"
      extra={
        <Space>
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
      <Space style={{ marginBottom: 12 }} wrap>
        <Typography.Text type="secondary">图例：</Typography.Text>
        <Tag color="#cf1322">已确认瓶颈</Tag>
        <Tag color="#fa8c16">疑似瓶颈</Tag>
        <Tag color="#722ed1">Serenity 小众环节</Tag>
        <Tag color="#eb2f96">溯源路径高亮</Tag>
        <Tag color="#1677ff">普通环节</Tag>
        <Tag color="#52c41a">上市公司</Tag>
        <Tag color="#8c8c8c">知识过期(stale)</Tag>
      </Space>
      <Spin spinning={loading}>
        <div ref={containerRef} style={{ width: "100%", height: 560, border: "1px solid #f0f0f0" }} />
      </Spin>
      {paths.length > 0 && (
        <Card size="small" title="Serenity 逆向溯源路径" style={{ marginTop: 12 }}>
          <List
            size="small"
            dataSource={paths.slice(0, 5)}
            renderItem={(p) => (
              <List.Item
                actions={[<a key="hl" onClick={() => highlightPath(p)}>高亮</a>]}
              >
                <Tag color="purple">{p.niche_product_name}</Tag>
                {p.hop_count} 跳 · 提示分 {p.serenity_hint} · {p.node_names.join(" → ")}
              </List.Item>
            )}
          />
        </Card>
      )}
    </Card>
  );
}
