import { useEffect, useState } from "react";
import {
  App as AntApp,
  Alert,
  Button,
  Card,
  Checkbox,
  Modal,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { useSearchParams } from "react-router-dom";
import {
  confirmCandidates,
  getCandidates,
  getDiagnosis,
  getStaleKnowledge,
  runCandidateFusionAgent,
  type Candidate,
  type DiagnosisItem,
} from "../lib/api";
import { useSector } from "../lib/sectorContext";
import AgentPageStrip from "../components/agent-session/AgentPageStrip";
import CandidateDossierDrawer from "../components/CandidateDossierDrawer";

const statusTag = (s: string) => {
  if (s === "confirmed") return <Tag color="green">已入池</Tag>;
  if (s === "rejected") return <Tag color="red">已否决</Tag>;
  return <Tag color="orange">待确认</Tag>;
};

const priorityTag = (p?: string) =>
  p === "P0" ? <Tag color="magenta">P0 双逻辑共振</Tag> : p ? <Tag>{p}</Tag> : null;

const edgeTag = (c: Candidate) => {
  const e = c.edge_assessment;
  if (!e) return null;
  if (e.priced_in === "high") return <Tag color="red">预期透支</Tag>;
  if (e.priced_in === "medium") return <Tag color="orange">预期偏高</Tag>;
  if (e.priced_in === "low") return <Tag color="green">预期差佳</Tag>;
  return <Tag>预期数据不足</Tag>;
};

const valueTag = (c: Candidate) => {
  const v = c.value_capture;
  if (!v) return null;
  if (v.captures_economics === "yes") return <Tag color="green">价值可捕获</Tag>;
  if (v.captures_economics === "partial") return <Tag color="orange">捕获有限</Tag>;
  if (v.captures_economics === "no") return <Tag color="red">利润不在此环节</Tag>;
  return <Tag>捕获数据不足</Tag>;
};

const bearTag = (c: Candidate) => {
  if (c.bear_status === "unrebutted_high") return <Tag color="red">空头待回应</Tag>;
  if (c.bear_status === "rebutted") return <Tag color="green">空头已回应</Tag>;
  return null;
};

const verdictColor: Record<string, string> = {
  retail_trap: "red",
  professional_alpha: "green",
  mixed: "orange",
};

function gateChecks(c: Candidate) {
  const edgeOk = c.edge_assessment?.priced_in === "low" || c.edge_assessment?.priced_in === "medium";
  const valueOk =
    c.value_capture?.captures_economics === "yes" || c.value_capture?.captures_economics === "partial";
  const bearOk = c.bear_status !== "unrebutted_high";
  return { edgeOk, valueOk, bearOk, allOk: edgeOk && valueOk && bearOk };
}

function DiagnosisTab({ sectorId }: { sectorId: string }) {
  const [items, setItems] = useState<DiagnosisItem[]>([]);
  useEffect(() => {
    getDiagnosis(sectorId).then((r) => setItems(r.items));
  }, [sectorId]);

  return (
    <>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="区分题材炒作（散户陷阱）与产业壁垒 Alpha（专业主升）"
      />
      <Table
        size="small"
        rowKey="stock_code"
        dataSource={items}
        pagination={false}
        columns={[
          { title: "代码", dataIndex: "stock_code", width: 90 },
          { title: "名称", dataIndex: "name" },
          {
            title: "诊断",
            dataIndex: "verdict_label",
            render: (_: string, r: DiagnosisItem) => (
              <Tag color={verdictColor[r.verdict]}>{r.verdict_label}</Tag>
            ),
          },
          { title: "散户分", dataIndex: "retail_score", width: 80 },
          { title: "专业分", dataIndex: "professional_score", width: 80 },
          { title: "建议", dataIndex: "advice", ellipsis: true },
        ]}
      />
    </>
  );
}

export default function CandidatesPage() {
  const { message } = AntApp.useApp();
  const { sectorId } = useSector();
  const [searchParams, setSearchParams] = useSearchParams();
  const pageTab = searchParams.get("tab") === "diagnosis" ? "diagnosis" : "pool";
  const [mode, setMode] = useState("fusion");
  const [items, setItems] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [fusionLoading, setFusionLoading] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [gated, setGated] = useState(false);
  const [gateMessage, setGateMessage] = useState<string | null>(null);
  const [staleCount, setStaleCount] = useState(0);
  const [dossierCode, setDossierCode] = useState<string | null>(null);

  const load = (m: string) => {
    if (!sectorId) return;
    setLoading(true);
    getCandidates(sectorId, m)
      .then((d) => {
        setItems(d.items);
        setGated(!!d.gated);
        setGateMessage(d.gate_message ?? null);
      })
      .finally(() => setLoading(false));
    getStaleKnowledge(sectorId).then((r) => setStaleCount(r.count));
  };

  useEffect(() => load(mode), [mode, sectorId]);

  const runFusion = async () => {
    setFusionLoading(true);
    try {
      await runCandidateFusionAgent({ sector_id: sectorId, mode: "fusion" });
      message.success("候选融合 Agent 运行完成");
      load(mode);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "融合失败");
    } finally {
      setFusionLoading(false);
    }
  };

  const act = (action: "confirmed" | "rejected", codes: string[]) => {
    if (!codes.length) {
      message.warning("请先选择标的");
      return;
    }
    const candidates = items.filter((c) => codes.includes(c.stock_code));
    let reason = "";
    let gateAck = { edge: false, value: false, bear: false };

    if (action === "confirmed") {
      const blocked = candidates.find((c) => c.bear_status === "unrebutted_high");
      if (blocked) {
        message.error(`${blocked.stock_code} 存在未回应的高severity空头，请先在论证工作台回应`);
        setDossierCode(blocked.stock_code);
        return;
      }
    }

    Modal.confirm({
      title: action === "confirmed" ? "确认入池 — 三道闸复核" : "否决",
      width: 520,
      content: (
        <div>
          {action === "confirmed" &&
            candidates.map((c) => {
              const g = gateChecks(c);
              return (
                <div key={c.stock_code} style={{ marginBottom: 12 }}>
                  <Typography.Text strong>
                    {c.stock_code} {c.name}
                  </Typography.Text>
                  <div style={{ marginTop: 4 }}>
                    <Tag color={g.edgeOk ? "green" : "red"}>预期差</Tag>
                    <Tag color={g.valueOk ? "green" : "orange"}>价值捕获</Tag>
                    <Tag color={g.bearOk ? "green" : "red"}>空头回应</Tag>
                  </div>
                </div>
              );
            })}
          {action === "confirmed" && (
            <Space direction="vertical" style={{ marginTop: 8 }}>
              <Checkbox onChange={(e) => (gateAck.edge = e.target.checked)}>
                已复核预期差（priced_in 非 high）
              </Checkbox>
              <Checkbox onChange={(e) => (gateAck.value = e.target.checked)}>
                已复核价值捕获逻辑
              </Checkbox>
              <Checkbox onChange={(e) => (gateAck.bear = e.target.checked)}>
                已回应或评估空头论点
              </Checkbox>
            </Space>
          )}
          <textarea
            placeholder="请填写理由（≥5 字），将写入审计日志"
            style={{ width: "100%", height: 80, marginTop: 12 }}
            onChange={(e) => (reason = e.target.value)}
          />
        </div>
      ),
      onOk: async () => {
        if (reason.trim().length < 5) {
          message.error("理由至少 5 个字");
          throw new Error("reason too short");
        }
        if (action === "confirmed" && (!gateAck.edge || !gateAck.value || !gateAck.bear)) {
          message.error("请勾选三道闸复核项");
          throw new Error("gates not checked");
        }
        await confirmCandidates({
          sector_id: sectorId,
          mode,
          stock_codes: codes,
          action,
          reason,
          operator: "analyst",
          gate_ack: action === "confirmed",
        });
        message.success(`已${action === "confirmed" ? "入池" : "否决"} ${codes.length} 个标的`);
        setSelected([]);
        load(mode);
      },
    });
  };

  const columns = [
    { title: "代码", dataIndex: "stock_code", width: 90 },
    { title: "名称", dataIndex: "name" },
    {
      title: "标签",
      render: (_: unknown, r: Candidate) => (
        <Space size={4} wrap>
          {priorityTag(r.priority)}
          {r.in_buy_side && <Tag color="geekblue">买方</Tag>}
          {r.in_serenity && <Tag color="purple">Serenity</Tag>}
        </Space>
      ),
    },
    { title: "环节", dataIndex: "product_name", width: 130 },
    {
      title: "提示分",
      dataIndex: "hint_score",
      width: 90,
      sorter: (a: Candidate, b: Candidate) => a.hint_score - b.hint_score,
      render: (v: number) => <b>{v}</b>,
    },
    {
      title: (
        <Tooltip title="入池三道闸：预期差 / 价值捕获 / 反证">
          <span>三道闸 ⓘ</span>
        </Tooltip>
      ),
      width: 230,
      render: (_: unknown, r: Candidate) => (
        <Space size={4} wrap>
          {edgeTag(r)}
          {valueTag(r)}
          {bearTag(r)}
        </Space>
      ),
    },
    { title: "逻辑", dataIndex: "rationale", ellipsis: true },
    { title: "状态", dataIndex: "status", width: 90, render: statusTag },
    {
      title: "操作",
      width: 220,
      render: (_: unknown, r: Candidate) => {
        const blocked = r.bear_status === "unrebutted_high";
        return (
          <Space>
            <Button size="small" onClick={() => setDossierCode(r.stock_code)}>
              论证
            </Button>
            <Button
              type="primary"
              size="small"
              disabled={blocked}
              onClick={() => act("confirmed", [r.stock_code])}
            >
              入池
            </Button>
            <Button size="small" danger onClick={() => act("rejected", [r.stock_code])}>
              否决
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <Card
      title="标的论证与入池（阶段④ · 双逻辑候选池）"
      extra={
        <Space>
          <Button loading={fusionLoading} onClick={runFusion}>
            运行候选融合 Agent
          </Button>
          <Button type="primary" disabled={!selected.length} onClick={() => act("confirmed", selected)}>
            批量入池（{selected.length}）
          </Button>
        </Space>
      }
    >
      {gated && gateMessage && (
        <Alert type="warning" showIcon message={gateMessage} style={{ marginBottom: 12 }} />
      )}
      {staleCount > 0 && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${staleCount} 个环节知识已过期，请在产业看板 / 图谱复核`}
        />
      )}
      <Tabs
        activeKey={pageTab}
        onChange={(k) => setSearchParams(k === "diagnosis" ? { tab: "diagnosis" } : {})}
        items={[
          {
            key: "pool",
            label: "候选池",
            children: (
              <>
                <Tabs
                  activeKey={mode}
                  onChange={setMode}
                  items={[
                    { key: "fusion", label: "双逻辑融合" },
                    { key: "buy_side", label: "买方专业" },
                    { key: "serenity", label: "Serenity 逆向" },
                  ]}
                />
                <Table
                  rowKey="stock_code"
                  loading={loading}
                  columns={columns as any}
                  dataSource={items}
                  rowSelection={{ selectedRowKeys: selected, onChange: (k) => setSelected(k as string[]) }}
                  pagination={false}
                  size="small"
                />
              </>
            ),
          },
          {
            key: "diagnosis",
            label: "智能诊断",
            children: <DiagnosisTab sectorId={sectorId} />,
          },
        ]}
      />
      <CandidateDossierDrawer
        open={!!dossierCode}
        sectorId={sectorId}
        stockCode={dossierCode}
        mode={mode}
        onClose={() => setDossierCode(null)}
        onAct={(action, codes) => act(action, codes)}
        onChanged={() => load(mode)}
      />
      <div style={{ marginTop: 16 }}>
        <AgentPageStrip
          sectorId={sectorId}
          focus="candidates"
          workflowStep={6}
          pageHint="本页 Agent：候选融合、多空对照、批量入池、智能诊断"
        />
      </div>
    </Card>
  );
}
