import { useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
import { Alert, Card, Col, Row, Statistic, Table, Tag, Typography } from "antd";
import { getDashboard, type DashboardData } from "../lib/api";

const SECTOR = "sector_ai_compute";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [gated, setGated] = useState(false);
  const [gateMsg, setGateMsg] = useState<string | null>(null);

  useEffect(() => {
    getDashboard(SECTOR).then((r) => {
      setData(r.dashboard);
      setGated(r.gated);
      setGateMsg(r.message ?? null);
    });
  }, []);

  if (!data) return null;

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

  return (
    <div>
      <Typography.Title level={4}>{data.sector_name} — 产业指标看板</Typography.Title>
      {gated && gateMsg && (
        <Alert type="warning" showIcon message={gateMsg} style={{ marginBottom: 16 }} />
      )}
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
            {
              title: "价格/出货同比",
              dataIndex: "price_or_shipment_yoy",
              render: (v: number | null) => (v != null ? `${(v * 100).toFixed(0)}%` : "—"),
            },
          ]}
        />
      </Card>
      <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
        {data.note}
      </Typography.Paragraph>
    </div>
  );
}
