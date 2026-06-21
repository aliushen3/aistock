import { useEffect, useState } from "react";
import { App as AntApp, Alert, Button, Card, Modal, Space, Table, Tabs, Tag, Tooltip } from "antd";
import { confirmCandidates, getCandidates, type Candidate } from "../lib/api";

const SECTOR = "sector_ai_compute";

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

export default function CandidatesPage() {
  const { message } = AntApp.useApp();
  const [mode, setMode] = useState("fusion");
  const [items, setItems] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [gated, setGated] = useState(false);
  const [gateMessage, setGateMessage] = useState<string | null>(null);

  const load = (m: string) => {
    setLoading(true);
    getCandidates(SECTOR, m)
      .then((d) => {
        setItems(d.items);
        setGated(!!d.gated);
        setGateMessage(d.gate_message ?? null);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => load(mode), [mode]);

  const act = (action: "confirmed" | "rejected", codes: string[]) => {
    if (!codes.length) {
      message.warning("请先选择标的");
      return;
    }
    let reason = "";
    Modal.confirm({
      title: action === "confirmed" ? "确认入池" : "否决",
      content: (
        <textarea
          placeholder="请填写理由（≥5 字），将写入审计日志"
          style={{ width: "100%", height: 80, marginTop: 8 }}
          onChange={(e) => (reason = e.target.value)}
        />
      ),
      onOk: async () => {
        if (reason.trim().length < 5) {
          message.error("理由至少 5 个字");
          throw new Error("reason too short");
        }
        await confirmCandidates({ sector_id: SECTOR, mode, stock_codes: codes, action, reason, operator: "analyst" });
        message.success(`已${action === "confirmed" ? "入池" : "否决"} ${codes.length} 个标的，已记录审计日志`);
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
          {r.tag && r.priority !== "P0" && <Tag>{r.tag}</Tag>}
          {r.role && <Tag color="blue">{r.role}</Tag>}
          {r.in_buy_side && <Tag color="geekblue">买方</Tag>}
          {r.in_serenity && <Tag color="purple">Serenity</Tag>}
        </Space>
      ),
    },
    { title: "环节", dataIndex: "product_name", width: 130 },
    {
      title: (
        <Tooltip title="提示分仅供排序，不构成投资建议">
          <span>提示分 ⓘ</span>
        </Tooltip>
      ),
      dataIndex: "hint_score",
      width: 90,
      sorter: (a: Candidate, b: Candidate) => a.hint_score - b.hint_score,
      render: (v: number) => <b>{v}</b>,
    },
    {
      title: (
        <Tooltip title="入池三道闸：预期差 / 价值捕获 / 反证；高severity空头未回应将阻断入池">
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
      width: 160,
      render: (_: unknown, r: Candidate) => {
        const blocked = r.bear_status === "unrebutted_high";
        return (
          <Space>
            <Tooltip title={blocked ? "存在未回应的高severity空头论点，请先在报告页回应（RebutBearCase）" : ""}>
              <Button
                type="primary"
                size="small"
                disabled={blocked}
                onClick={() => act("confirmed", [r.stock_code])}
              >
                入池
              </Button>
            </Tooltip>
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
      title="双逻辑候选池（须人工确认后方可入正式池）"
      extra={
        <Button type="primary" disabled={!selected.length} onClick={() => act("confirmed", selected)}>
          批量入池（{selected.length}）
        </Button>
      }
    >
      {gated && gateMessage && (
        <Alert type="warning" showIcon message={gateMessage} style={{ marginBottom: 12 }} />
      )}
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
    </Card>
  );
}
