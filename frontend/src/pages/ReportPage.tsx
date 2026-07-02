import { useEffect, useState } from "react";
import { App as AntApp, Alert, Button, Card, Descriptions, Input, List, Modal, Space, Steps, Tag, Typography } from "antd";
import {
  generateReport,
  reviewReport,
  executeOntologyAction,
  runBearCaseAgent,
  getBearCases,
  rebutBearCase,
  type BearCase,
  type Report,
} from "../lib/api";
import { useSector } from "../lib/sectorContext";
import AgentPageStrip from "../components/agent-session/AgentPageStrip";

const sev = (s: string) => (s === "高" || s === "high" ? "red" : s === "中" || s === "medium" ? "orange" : "green");
const confColor = (c: string) => (c === "high" ? "green" : c === "medium" ? "orange" : "default");

export default function ReportPage() {
  const { message } = AntApp.useApp();
  const { sectorId } = useSector();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [bears, setBears] = useState<BearCase[]>([]);
  const [bearLoading, setBearLoading] = useState(false);

  useEffect(() => {
    setReport(null);
    setBears([]);
  }, [sectorId]);

  const runBear = () => {
    if (!sectorId) return;
    setBearLoading(true);
    runBearCaseAgent({ sector_id: sectorId, mode: "fusion" })
      .then((b) => setBears(b.bear_cases))
      .finally(() => setBearLoading(false));
  };

  const refreshBears = () => getBearCases(sectorId).then(setBears);

  const rebut = (bear: BearCase) => {
    let text = "";
    Modal.confirm({
      title: `回应空头论点：${bear.dimension}`,
      content: (
        <Input.TextArea
          rows={3}
          placeholder="正面回应该风险（≥10 字），将记录审计日志"
          onChange={(e) => (text = e.target.value)}
        />
      ),
      onOk: async () => {
        if (text.trim().length < 10) {
          message.error("回应至少 10 个字");
          throw new Error("rebuttal too short");
        }
        await rebutBearCase(bear.bear_id, text);
        message.success("已回应空头论点（RebutBearCase）");
        await refreshBears();
      },
    });
  };

  const gen = () => {
    if (!sectorId) return;
    setLoading(true);
    generateReport(sectorId, "fusion")
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
      title="研究报告（阶段④ 论证产出物 — GraphRAG 草稿，须人工审核发布）"
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
            {report.rag_context && (
              <Descriptions.Item label="混合检索">
                {report.rag_context.retrieval_count} 条（{report.rag_context.retrieval_mode}）
              </Descriptions.Item>
            )}
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

          <Space style={{ justifyContent: "space-between", width: "100%" }}>
            <Typography.Title level={5} style={{ margin: 0 }}>
              多空对照 · 独立看空论点（BearCase）
            </Typography.Title>
            <Button size="small" loading={bearLoading} onClick={runBear}>
              运行反证 Agent
            </Button>
          </Space>
          {bears.length === 0 ? (
            <Alert
              type="info"
              showIcon
              message="尚无看空论点。点击「运行反证 Agent」独立检索反面证据，与看多论点等强对抗；高severity 未回应将阻断入池。"
            />
          ) : (
            <List
              size="small"
              bordered
              dataSource={bears}
              renderItem={(b) => (
                <List.Item
                  actions={[
                    b.rebuttal_status === "rebutted" ? (
                      <Tag color="green">已回应</Tag>
                    ) : (
                      <Button size="small" danger onClick={() => rebut(b)}>
                        回应
                      </Button>
                    ),
                  ]}
                >
                  <Space direction="vertical" size={2} style={{ width: "100%" }}>
                    <Space wrap>
                      <Tag color="volcano">{b.stock_code}</Tag>
                      <Tag>{b.dimension}</Tag>
                      <Tag color={sev(b.severity)}>severity: {b.severity}</Tag>
                      <span>{b.risk}</span>
                    </Space>
                    <Typography.Text type="secondary">
                      证伪条件：{b.what_would_confirm || "—"}　引用：{b.citations.join(", ") || "—"}
                    </Typography.Text>
                    {b.rebuttal && <Typography.Text type="success">回应：{b.rebuttal}</Typography.Text>}
                  </Space>
                </List.Item>
              )}
            />
          )}

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
      <div style={{ marginTop: 16 }}>
        <AgentPageStrip
          sectorId={sectorId}
          focus="report"
          workflowStep={5}
          pageHint="本页 Agent：生成报告草稿、运行反证 Agent、审核发布"
        />
      </div>
    </Card>
  );
}
