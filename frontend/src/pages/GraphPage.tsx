import { useEffect, useRef, useState } from "react";
import { Card, Select, Space, Spin, Tag, Typography } from "antd";
import G6 from "@antv/g6";
import { getSectorGraph, getSectors, type GraphNode } from "../lib/api";

const PRODUCT_COLOR = (n: GraphNode) => {
  if (n.bottleneck_status === "bottleneck_confirmed") return "#cf1322";
  if (n.serenity_niche) return "#722ed1";
  if (n.bottleneck_status === "bottleneck_hint") return "#fa8c16";
  return "#1677ff";
};

export default function GraphPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [sectors, setSectors] = useState<{ id: string; name: string }[]>([]);
  const [sectorId, setSectorId] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSectors().then((s) => {
      setSectors(s);
      if (s.length) setSectorId(s[0].id);
    });
  }, []);

  useEffect(() => {
    if (!sectorId || !containerRef.current) return;
    setLoading(true);
    getSectorGraph(sectorId).then((g) => {
      const nodes = g.nodes.map((n) => ({
        id: n.id,
        label: n.type === "product" ? `${n.label}\n${n.hint_score ?? ""}` : n.label,
        type: n.type === "company" ? "rect" : "circle",
        size: n.type === "company" ? [110, 32] : 48,
        style: {
          fill: n.type === "company" ? "#f6ffed" : PRODUCT_COLOR(n),
          stroke: n.type === "company" ? "#52c41a" : "#fff",
          lineWidth: 2,
        },
        labelCfg: { style: { fill: n.type === "company" ? "#135200" : "#fff", fontSize: 11 } },
      }));
      const edges = g.edges.map((e) => ({
        source: e.source,
        target: e.target,
        style: {
          stroke: e.type === "PRODUCES" ? "#b7eb8f" : "#bfbfbf",
          lineDash: e.type === "PRODUCES" ? [4, 4] : undefined,
          endArrow: true,
        },
      }));

      const width = containerRef.current!.scrollWidth || 1000;
      if (graphRef.current) graphRef.current.destroy();
      const graph = new G6.Graph({
        container: containerRef.current!,
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
      graphRef.current = graph;
      setLoading(false);
    });
    return () => {
      if (graphRef.current) {
        graphRef.current.destroy();
        graphRef.current = null;
      }
    };
  }, [sectorId]);

  return (
    <Card
      title="产业链拓扑（沿 UPSTREAM_OF 自上游 → 终端）"
      extra={
        <Select
          value={sectorId}
          style={{ width: 160 }}
          options={sectors.map((s) => ({ value: s.id, label: s.name }))}
          onChange={setSectorId}
        />
      }
    >
      <Space style={{ marginBottom: 12 }} wrap>
        <Typography.Text type="secondary">图例：</Typography.Text>
        <Tag color="#cf1322">已确认瓶颈</Tag>
        <Tag color="#fa8c16">疑似瓶颈</Tag>
        <Tag color="#722ed1">Serenity 小众环节</Tag>
        <Tag color="#1677ff">普通环节</Tag>
        <Tag color="#52c41a">上市公司</Tag>
        <Typography.Text type="secondary">（产品节点数字为瓶颈提示分）</Typography.Text>
      </Space>
      <Spin spinning={loading}>
        <div ref={containerRef} style={{ width: "100%", height: 560, border: "1px solid #f0f0f0" }} />
      </Spin>
    </Card>
  );
}
