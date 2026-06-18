import { useState } from "react";
import { App as AntApp, Alert, Button, Card, Descriptions, List, Space, Steps, Tag, Typography } from "antd";
import { generateReport, reviewReport, executeOntologyAction, type Report } from "../lib/api";

const SECTOR = "sector_ai_compute";

const sev = (s: string) => (s === "高" ? "red" : s === "中" ? "orange" : "green");
const confColor = (c: string) => (c === "high" ? "green" : c === "medium" ? "orange" : "default");

export default function ReportPage() {
  const { message } = AntApp.useApp();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);

  const gen = () => {
    setLoading(true);
    generateReport(SECTOR, "fusion")
      .then(setReport)
      .finally(() => setLoading(false));
  };

  const review = async (action: string) => {
    if (!report) return;
    if (action === "approve") {
      try {
        await executeOntologyAction(
          "PublishReport",
          { type: "ResearchReport", id: report.report_id },
          { comments: "逻辑链完整" },
          "analyst"
        );
        setReport({ ...report, status: "published" });
        message.success("报告已发布（PublishReport Action）");
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: { message?: string } | string } } };
        const detail = err.response?.data?.detail;
        const msg = typeof detail === "object" ? detail?.message : detail;
        message.error(msg || "发布失败");
      }
      return;
    }
    const r = await reviewReport(report.report_id, action, "需修订");
    setReport({ ...report, status: r.new_status });
    message.success("已退回草稿");
  };

  return (
    <Card
      title="AI 投研逻辑报告（GraphRAG 草稿，须人工审核发布）"
      extra={
        <Button type="primary" loading={loading} onClick={gen}>
          生成报告草稿
        </Button>
      }
    >
      {!report ? (
        <Alert type="info" showIcon message="点击「生成报告草稿」基于图谱事实生成可追溯逻辑链" />
      ) : (
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          <Descriptions size="small" column={3} bordered>
            <Descriptions.Item label="报告号">{report.report_id}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={report.status === "published" ? "green" : "orange"}>{report.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="生成方式">{report.generated_by}</Descriptions.Item>
            <Descriptions.Item label="未溯源论断" span={3}>
              {report.unverified_claims.length === 0 ? (
                <Tag color="green">0（全部可溯源）</Tag>
              ) : (
                <Tag color="red">{report.unverified_claims.length}</Tag>
              )}
            </Descriptions.Item>
          </Descriptions>

          <Typography.Title level={5}>投资逻辑链</Typography.Title>
          <Steps
            direction="vertical"
            size="small"
            current={report.logic_chain.length}
            items={report.logic_chain.map((s) => ({
              title: (
                <Space>
                  <Tag>{s.type}</Tag>
                  <Tag color={confColor(s.confidence)}>{s.confidence}</Tag>
                  {s.human_confirmed && <Tag color="green">人工确认</Tag>}
                  <span>引用 {s.citations.join(", ") || "—"}</span>
                </Space>
              ),
              description: s.claim,
            }))}
          />

          <Typography.Title level={5}>反证 Checklist（风险提示）</Typography.Title>
          <Space wrap>
            {report.counter_arguments.map((c) => (
              <Tag key={c.risk} color={sev(c.severity)}>
                {c.risk}：{c.severity}
              </Tag>
            ))}
          </Space>
          <List
            size="small"
            dataSource={report.counter_arguments}
            renderItem={(c) => (
              <List.Item>
                <Tag color={sev(c.severity)}>{c.risk}</Tag>
                {c.note}
              </List.Item>
            )}
          />

          <Typography.Title level={5}>证据引用</Typography.Title>
          <List
            size="small"
            bordered
            dataSource={report.citations}
            renderItem={(c) => (
              <List.Item>
                <Typography.Text strong>[{c.ref_id}]</Typography.Text>&nbsp;
                <Tag>{c.source_type}</Tag> {c.source_ref} — {c.excerpt}
              </List.Item>
            )}
          />

          <Alert type="warning" showIcon message={report.disclaimer} />

          <Space>
            <Button type="primary" disabled={report.status === "published"} onClick={() => review("approve")}>
              审核通过并发布
            </Button>
            <Button danger onClick={() => review("reject")}>
              退回修订
            </Button>
          </Space>
        </Space>
      )}
    </Card>
  );
}
