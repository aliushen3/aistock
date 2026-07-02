import { useEffect, useState } from "react";
import {
  App as AntApp,
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Input,
  List,
  Modal,
  Row,
  Space,
  Spin,
  Steps,
  Tag,
  Typography,
} from "antd";
import {
  getCandidateDossier,
  rebutBearCase,
  type BearCase,
  type Candidate,
  type CandidateDossier,
} from "../lib/api";

const SEVERITY_COLOR: Record<string, string> = { high: "red", medium: "orange", low: "green" };
const VERDICT_COLOR: Record<string, string> = {
  retail_trap: "red",
  professional_alpha: "green",
  mixed: "orange",
};

function pct(v?: number | null) {
  return v === null || v === undefined ? "—" : `${Math.round(v)}%`;
}

function EdgeGateCard({ c }: { c: Candidate }) {
  const e = c.edge_assessment;
  const tag =
    e?.priced_in === "high" ? (
      <Tag color="red">预期透支</Tag>
    ) : e?.priced_in === "medium" ? (
      <Tag color="orange">预期偏高</Tag>
    ) : e?.priced_in === "low" ? (
      <Tag color="green">预期差佳</Tag>
    ) : (
      <Tag>数据不足</Tag>
    );
  return (
    <Card size="small" title={<Space>闸一 · 预期差{tag}</Space>}>
      <Descriptions size="small" column={1} colon>
        <Descriptions.Item label="PE 历史分位">{pct(e?.pe_percentile)}</Descriptions.Item>
        <Descriptions.Item label="成交额分位（拥挤度）">{pct(e?.crowding_percentile)}</Descriptions.Item>
        <Descriptions.Item label="机构覆盖">{e?.analyst_coverage ?? "—"} 家</Descriptions.Item>
      </Descriptions>
      {e?.degraded && (
        <Typography.Text type="warning" style={{ fontSize: 12 }}>
          {e.reason || "数据缺失，无法完整评估 price-in（宁缺勿造）"}
        </Typography.Text>
      )}
    </Card>
  );
}

function ValueGateCard({ c }: { c: Candidate }) {
  const v = c.value_capture;
  const tag =
    v?.captures_economics === "yes" ? (
      <Tag color="green">价值可捕获</Tag>
    ) : v?.captures_economics === "partial" ? (
      <Tag color="orange">捕获有限</Tag>
    ) : v?.captures_economics === "no" ? (
      <Tag color="red">利润不在此环节</Tag>
    ) : (
      <Tag>数据不足</Tag>
    );
  return (
    <Card size="small" title={<Space>闸二 · 价值捕获{tag}</Space>}>
      <Descriptions size="small" column={1} colon>
        <Descriptions.Item label="毛利率">
          {v?.gross_margin === null || v?.gross_margin === undefined
            ? "—"
            : `${(v.gross_margin * 100).toFixed(1)}%`}
        </Descriptions.Item>
        <Descriptions.Item label="环节地位">
          {v?.market_rank ? `行业第 ${v.market_rank}` : "—"}
        </Descriptions.Item>
        <Descriptions.Item label="定价机制">
          {v?.pricing_mechanism === "contract"
            ? "长协锁价（弹性弱）"
            : v?.pricing_mechanism === "market"
              ? "市场定价（有弹性）"
              : "—"}
        </Descriptions.Item>
      </Descriptions>
      {v?.degraded && (
        <Typography.Text type="warning" style={{ fontSize: 12 }}>
          {v.reason || "数据缺失，无法完整评估价值捕获（宁缺勿造）"}
        </Typography.Text>
      )}
    </Card>
  );
}

function BearGateCard({ bears }: { bears: BearCase[] }) {
  const unrebuttedHigh = bears.filter(
    (b) => b.severity === "high" && b.rebuttal_status === "unrebutted"
  ).length;
  const rebutted = bears.filter((b) => b.rebuttal_status === "rebutted").length;
  const tag = unrebuttedHigh ? (
    <Tag color="red">高severity 待回应 ×{unrebuttedHigh}</Tag>
  ) : bears.length && rebutted === bears.length ? (
    <Tag color="green">空头已全部回应</Tag>
  ) : bears.length ? (
    <Tag color="orange">部分待回应</Tag>
  ) : (
    <Tag>暂无空头论点</Tag>
  );
  return (
    <Card size="small" title={<Space>闸三 · 反证{tag}</Space>}>
      <Descriptions size="small" column={1} colon>
        <Descriptions.Item label="空头论点">{bears.length} 条</Descriptions.Item>
        <Descriptions.Item label="已回应">{rebutted} 条</Descriptions.Item>
      </Descriptions>
      {unrebuttedHigh > 0 && (
        <Typography.Text type="danger" style={{ fontSize: 12 }}>
          高severity 空头未回应将阻断入池（流程硬约束）
        </Typography.Text>
      )}
    </Card>
  );
}

interface Props {
  open: boolean;
  sectorId: string;
  stockCode: string | null;
  mode: string;
  onClose: () => void;
  /** 触发父页面的入池/否决流程（复用三道闸确认 Modal） */
  onAct: (action: "confirmed" | "rejected", codes: string[]) => void;
  onChanged?: () => void;
}

/** 标的论证工作台：单标的看多链 vs 空头论点并排 + 三道闸依据 + rebut + 入池 */
export default function CandidateDossierDrawer({
  open,
  sectorId,
  stockCode,
  mode,
  onClose,
  onAct,
  onChanged,
}: Props) {
  const { message } = AntApp.useApp();
  const [dossier, setDossier] = useState<CandidateDossier | null>(null);
  const [loading, setLoading] = useState(false);

  const load = () => {
    if (!stockCode || !open) return;
    setLoading(true);
    getCandidateDossier(sectorId, stockCode, mode)
      .then(setDossier)
      .catch(() => message.error("加载标的论证档案失败"))
      .finally(() => setLoading(false));
  };

  useEffect(load, [sectorId, stockCode, mode, open]);

  const handleRebut = (bear: BearCase) => {
    let rebuttal = "";
    Modal.confirm({
      title: `回应空头论点 — ${bear.risk}`,
      width: 520,
      content: (
        <div>
          <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
            证伪条件：{bear.what_would_confirm || "—"}
          </Typography.Paragraph>
          <Input.TextArea
            rows={4}
            placeholder="正面回应该风险（≥10 字），将写入审计日志并纳入证伪条件跟踪"
            onChange={(e) => (rebuttal = e.target.value)}
          />
        </div>
      ),
      onOk: async () => {
        if (rebuttal.trim().length < 10) {
          message.error("回应至少 10 个字");
          throw new Error("rebuttal too short");
        }
        await rebutBearCase(bear.bear_id, rebuttal);
        message.success("已回应空头论点，证伪条件将持续跟踪");
        load();
        onChanged?.();
      },
    });
  };

  const c = dossier?.candidate;
  const bears = dossier?.bear_cases ?? [];
  const blocked = bears.some((b) => b.severity === "high" && b.rebuttal_status === "unrebutted");

  return (
    <Drawer
      title={
        c ? (
          <Space wrap>
            <Typography.Text strong>
              {c.stock_code} {c.name}
            </Typography.Text>
            {c.priority === "P0" && <Tag color="magenta">P0 双逻辑共振</Tag>}
            {c.in_buy_side && <Tag color="geekblue">买方</Tag>}
            {c.in_serenity && <Tag color="purple">Serenity</Tag>}
            <Tag>{c.product_name}</Tag>
          </Space>
        ) : (
          "标的论证工作台"
        )
      }
      placement="right"
      width={Math.min(980, window.innerWidth - 48)}
      open={open}
      onClose={onClose}
      extra={
        c && c.status === "pending" ? (
          <Space>
            <Button danger onClick={() => onAct("rejected", [c.stock_code])}>
              否决
            </Button>
            <Button type="primary" disabled={blocked} onClick={() => onAct("confirmed", [c.stock_code])}>
              入池（过三道闸）
            </Button>
          </Space>
        ) : c ? (
          <Tag color={c.status === "confirmed" ? "green" : "red"}>
            {c.status === "confirmed" ? "已入池" : "已否决"}
          </Tag>
        ) : null
      }
    >
      <Spin spinning={loading}>
        {blocked && (
          <Alert
            type="error"
            showIcon
            style={{ marginBottom: 12 }}
            message="存在未回应的高severity空头论点，入池被阻断 — 请先逐条正面回应（右侧看空区）"
          />
        )}

        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col span={8}>{c && <EdgeGateCard c={c} />}</Col>
          <Col span={8}>{c && <ValueGateCard c={c} />}</Col>
          <Col span={8}>
            <BearGateCard bears={bears} />
          </Col>
        </Row>

        <Row gutter={12}>
          <Col span={12}>
            <Card
              size="small"
              title={
                <Space>
                  <Tag color="green">看多</Tag>
                  <span>逻辑链</span>
                  {dossier?.bull?.report_status && <Tag>{dossier.bull.report_status}</Tag>}
                </Space>
              }
            >
              {c?.rationale && (
                <Typography.Paragraph style={{ fontSize: 13 }}>{c.rationale}</Typography.Paragraph>
              )}
              {dossier?.bull?.thesis_summary && (
                <Alert type="success" message={dossier.bull.thesis_summary} style={{ marginBottom: 12 }} />
              )}
              {dossier?.bull?.logic_chain?.length ? (
                <Steps
                  direction="vertical"
                  size="small"
                  current={-1}
                  items={dossier.bull.logic_chain.map((s) => ({
                    title: (
                      <Space size={4} wrap>
                        <Tag>{s.type}</Tag>
                        <Typography.Text style={{ fontSize: 13 }}>{s.claim}</Typography.Text>
                      </Space>
                    ),
                    description: (
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        置信度 {s.confidence}
                        {s.citations?.length ? ` · 引用 ${s.citations.join(", ")}` : " · 无引用"}
                        {s.human_confirmed ? " · 已人工确认" : ""}
                      </Typography.Text>
                    ),
                  }))}
                />
              ) : (
                <Empty
                  description="暂无看多报告 — 可在 Agent 会话运行「生成报告」"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              )}
            </Card>
          </Col>
          <Col span={12}>
            <Card
              size="small"
              title={
                <Space>
                  <Tag color="red">看空</Tag>
                  <span>空头论点（独立检索，等强对抗）</span>
                </Space>
              }
            >
              {bears.length ? (
                <List
                  size="small"
                  dataSource={bears}
                  renderItem={(b) => (
                    <List.Item
                      actions={
                        b.rebuttal_status === "unrebutted"
                          ? [
                              <Button key="rebut" size="small" onClick={() => handleRebut(b)}>
                                回应
                              </Button>,
                            ]
                          : undefined
                      }
                    >
                      <List.Item.Meta
                        title={
                          <Space size={4} wrap>
                            <Tag color={SEVERITY_COLOR[b.severity]}>{b.severity}</Tag>
                            <Tag>{b.dimension}</Tag>
                            <Typography.Text style={{ fontSize: 13 }}>{b.risk}</Typography.Text>
                          </Space>
                        }
                        description={
                          <Space direction="vertical" size={2} style={{ fontSize: 12 }}>
                            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                              证伪条件：{b.what_would_confirm || "—"}
                            </Typography.Text>
                            {b.rebuttal_status === "rebutted" ? (
                              <Typography.Text style={{ fontSize: 12 }}>
                                <Tag color="green">已回应</Tag>
                                {b.rebuttal}
                              </Typography.Text>
                            ) : (
                              <Tag color="red">未回应</Tag>
                            )}
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
                />
              ) : (
                <Empty
                  description="暂无空头论点 — 可在 Agent 会话运行「反证扫描」"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              )}
            </Card>
          </Col>
        </Row>

        {dossier?.diagnosis && (
          <Card size="small" title="智能诊断（散户陷阱 vs 专业 Alpha）" style={{ marginTop: 12 }}>
            <Space wrap>
              <Tag color={VERDICT_COLOR[dossier.diagnosis.verdict]}>
                {dossier.diagnosis.verdict_label}
              </Tag>
              <Typography.Text type="secondary">
                散户分 {dossier.diagnosis.retail_score} · 专业分 {dossier.diagnosis.professional_score}
              </Typography.Text>
              <Typography.Text style={{ fontSize: 13 }}>{dossier.diagnosis.advice}</Typography.Text>
            </Space>
          </Card>
        )}

        <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 12 }}>
          {dossier?.note} · 系统输出仅供投研参考，不构成投资建议。
        </Typography.Paragraph>
      </Spin>
    </Drawer>
  );
}
