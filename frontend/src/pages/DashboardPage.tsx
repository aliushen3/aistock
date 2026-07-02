import { useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
import { App as AntApp, Alert, Button, Card, Col, Empty, List, Row, Space, Spin, Statistic, Table, Tag, Typography } from "antd";
import { Link } from "react-router-dom";
import WorkflowEmptyGuide from "../components/WorkflowEmptyGuide";
import {
  getCandidates,
  getDashboard,
  getSectorWorkflowStatus,
  getStaleKnowledge,
  runMonitorWatchAgent,
  type Candidate,
  type DashboardData,
  type StaleKnowledgeItem,
} from "../lib/api";
import { useSector } from "../lib/sectorContext";

/** 正式池标的的逻辑健康度：保鲜 / 瓶颈生命周期 / 空头回应 / 预期与价值标注 */
function PortfolioHealthTable({
  portfolio,
  staleProductIds,
  productStatus,
}: {
  portfolio: Candidate[];
  staleProductIds: Set<string>;
  productStatus: Map<string, string>;
}) {
  if (!portfolio.length) {
    return (
      <Empty
        description="正式池为空 — 请在「标的论证」页完成三道闸并入池"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    );
  }
  const healthTags = (c: Candidate) => {
    const tags = [];
    const bnStatus = c.product_id ? productStatus.get(c.product_id) : undefined;
    if (c.product_id && staleProductIds.has(c.product_id)) {
      tags.push(<Tag key="stale" color="orange">环节知识过期</Tag>);
    }
    if (bnStatus === "bottleneck_easing" || bnStatus === "bottleneck_expired") {
      tags.push(<Tag key="easing" color="red">瓶颈缓解/失效 — 建议复核</Tag>);
    }
    if (c.bear_status === "unrebutted_high") {
      tags.push(<Tag key="bear" color="red">新空头待回应</Tag>);
    }
    if (c.edge_assessment?.priced_in === "high") {
      tags.push(<Tag key="edge" color="orange">预期透支</Tag>);
    }
    if (!tags.length) tags.push(<Tag key="ok" color="green">逻辑健康</Tag>);
    return tags;
  };
  return (
    <Table
      size="small"
      pagination={false}
      rowKey="stock_code"
      dataSource={portfolio}
      columns={[
        { title: "代码", dataIndex: "stock_code", width: 90 },
        { title: "名称", dataIndex: "name", width: 120 },
        { title: "环节", dataIndex: "product_name", width: 130 },
        {
          title: "逻辑健康度",
          render: (_: unknown, c: Candidate) => <Space size={4} wrap>{healthTags(c)}</Space>,
        },
        {
          title: "入池逻辑",
          dataIndex: "rationale",
          ellipsis: true,
        },
        {
          title: "操作",
          width: 100,
          render: () => (
            <Link to="/candidates?tab=pool" title="回到论证工作台复核">
              去复核 →
            </Link>
          ),
        },
      ]}
    />
  );
}

export default function DashboardPage() {
  const { message } = AntApp.useApp();
  const { sectorId } = useSector();
  const [data, setData] = useState<DashboardData | null>(null);
  const [gated, setGated] = useState(false);
  const [gateMsg, setGateMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<{ products: number; companies: number; drafts: number }>();
  const [staleItems, setStaleItems] = useState<StaleKnowledgeItem[]>([]);
  const [portfolio, setPortfolio] = useState<Candidate[]>([]);
  const [monitorLoading, setMonitorLoading] = useState(false);

  const load = () => {
    if (!sectorId) return;
    setLoading(true);
    setData(null);
    Promise.all([
      getDashboard(sectorId),
      getSectorWorkflowStatus(sectorId),
      getStaleKnowledge(sectorId),
      getCandidates(sectorId, "fusion").catch(() => null),
    ])
      .then(([dash, ws, stale, pool]) => {
        setData(dash.dashboard);
        setGated(dash.gated);
        setGateMsg(dash.message ?? null);
        setStats(ws.graph_stats);
        setStaleItems(stale.items ?? []);
        setPortfolio((pool?.items ?? []).filter((c) => c.status === "confirmed"));
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, [sectorId]);

  const runMonitor = async () => {
    setMonitorLoading(true);
    try {
      const r = await runMonitorWatchAgent({ sector_id: sectorId });
      message.success((r.agent_summary as string) || "监控 Agent 扫描完成，告警已更新");
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "监控 Agent 运行失败");
    } finally {
      setMonitorLoading(false);
    }
  };

  if (loading) {
    return <Spin />;
  }

  if (!data || data.product_cards.length === 0) {
    return (
      <div>
        <Typography.Title level={4}>组合跟踪</Typography.Title>
        <WorkflowEmptyGuide
          step={4}
          sectorId={sectorId}
          stats={stats}
          gated={gated}
          gateMessage={gateMsg ?? undefined}
        />
      </div>
    );
  }

  const capChart = {
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: data.product_cards.map((p) => p.product_name) },
    yAxis: { type: "value", max: 1, axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` } },
    series: [
      {
        name: "产能利用率",
        type: "bar",
        data: data.product_cards.map((p) => p.capacity_utilization ?? 0),
        itemStyle: { color: "#1677ff" },
      },
    ],
  };

  const sectorMetrics = data.sector_metrics.map((m) => ({
    key: m.metric_key,
    label: m.metric_label,
    value: m.unit === "ratio" ? `${(m.value * 100).toFixed(1)}%` : m.value,
    period: m.period,
  }));

  const staleProductIds = new Set(staleItems.map((s) => s.product_id));
  const productStatus = new Map(data.product_cards.map((p) => [p.product_id, p.bottleneck_status]));

  return (
    <div>
      <Space align="baseline" style={{ justifyContent: "space-between", width: "100%" }}>
        <Typography.Title level={4}>{data.sector_name} — 组合跟踪（阶段⑤ 持续跟踪）</Typography.Title>
        <Button loading={monitorLoading} onClick={runMonitor}>
          运行监控 Agent
        </Button>
      </Space>
      {stats && (
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
          图谱：{stats.products} 产品 · {stats.companies} 成分股 ·
          监控 Agent 每小时自动扫描（保鲜 / 瓶颈缓解 / 指标异动），告警进入首页决策收件箱
        </Typography.Text>
      )}
      {gated && gateMsg && (
        <Alert type="warning" showIcon message={gateMsg} style={{ marginBottom: 16 }} />
      )}
      <Card
        title={`正式池 · 逻辑健康度（${portfolio.length} 个标的）`}
        style={{ marginBottom: 16 }}
        size="small"
      >
        <PortfolioHealthTable
          portfolio={portfolio}
          staleProductIds={staleProductIds}
          productStatus={productStatus}
        />
      </Card>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        {sectorMetrics.map((m) => (
          <Col key={m.key} xs={12} sm={8} lg={6}>
            <Card size="small">
              <Statistic title={`${m.label} (${m.period})`} value={m.value} />
            </Card>
          </Col>
        ))}
      </Row>
      <Card title="环节产能利用率" style={{ marginBottom: 16 }}>
        <ReactECharts option={capChart} style={{ height: 320 }} />
      </Card>
      {data.material_metrics && data.material_metrics.length > 0 && (
        <Card title="材料行情" style={{ marginBottom: 16 }}>
          <Table
            size="small"
            pagination={false}
            rowKey="material_key"
            dataSource={data.material_metrics}
            columns={[
              { title: "材料", dataIndex: "material_key" },
              {
                title: "现价",
                dataIndex: "price",
                render: (v: number | null, r: { unit: string }) => (v != null ? `${v} ${r.unit}` : "—"),
              },
              {
                title: "同比",
                dataIndex: "price_yoy",
                render: (v: number | null) =>
                  v != null ? (
                    <span style={{ color: v >= 0 ? "#cf1322" : "#3f8600" }}>{(v * 100).toFixed(1)}%</span>
                  ) : (
                    "—"
                  ),
              },
              { title: "日期", dataIndex: "period", width: 120 },
            ]}
          />
        </Card>
      )}
      <Card title="环节指标卡片">
        <Table
          size="small"
          pagination={false}
          dataSource={data.product_cards}
          rowKey="product_id"
          columns={[
            { title: "环节", dataIndex: "product_name" },
            {
              title: "瓶颈状态",
              dataIndex: "bottleneck_status",
              render: (v: string) => (
                <Tag color={v === "bottleneck_confirmed" ? "red" : v === "bottleneck_hint" ? "orange" : "default"}>
                  {v}
                </Tag>
              ),
            },
            {
              title: "产能利用率",
              dataIndex: "capacity_utilization",
              render: (v: number | null) => (v != null ? `${(v * 100).toFixed(0)}%` : "—"),
            },
          ]}
        />
      </Card>
      {staleItems.length > 0 && (
        <Card title="知识保鲜 — 过期数据待复核" style={{ marginTop: 16 }} size="small">
          <List
            size="small"
            dataSource={staleItems.slice(0, 10)}
            renderItem={(item) => (
              <List.Item>
                <Link to={`/products/${item.product_id}`}>{item.product_name}</Link>
                <Tag color="default">stale</Tag>
              </List.Item>
            )}
          />
        </Card>
      )}
      <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
        {data.note}
      </Typography.Paragraph>
    </div>
  );
}
