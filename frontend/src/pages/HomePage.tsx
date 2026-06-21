import { useEffect, useState } from "react";

import {

  App as AntApp,

  Alert,

  Button,

  Card,

  Col,

  Input,

  List,

  Row,

  Space,

  Tag,

  Typography,

} from "antd";

import { Link } from "react-router-dom";

import AgentConsole from "../components/AgentConsole";

import WatchlistPanel from "../components/WatchlistPanel";

import WorkflowGuide from "../components/WorkflowGuide";

import {

  confirmSector,

  getAlerts,

  getDataAdapters,

  getGlobalAlerts,

  getHealth,

  getSectors,

  syncSectorMetrics,

  type Sector,

  type WatchlistItem,

} from "../lib/api";



const statusTag = (s: Sector) => {

  if (s.status === "beta_confirmed" && s.human_confirmed) {

    return <Tag color="green">已确认景气</Tag>;

  }

  if (s.status === "rejected") return <Tag color="red">已驳回</Tag>;

  return <Tag color="orange">待确认 beta_candidate</Tag>;

};



export default function HomePage() {

  const { message } = AntApp.useApp();

  const [sectors, setSectors] = useState<Sector[]>([]);

  const [reason, setReason] = useState("");

  const [loading, setLoading] = useState(false);

  const [syncLoading, setSyncLoading] = useState(false);

  const [alerts, setAlerts] = useState<{ level: string; type: string; message: string }[]>([]);

  const [components, setComponents] = useState<Record<string, unknown>>({});

  const [adapters, setAdapters] = useState<{ name: string; mode: string; live_configured?: boolean }[]>([]);

  const [agentFocus, setAgentFocus] = useState("AI算力");

  const [agentQuery, setAgentQuery] = useState("");

  const [activeSectorId, setActiveSectorId] = useState("sector_ai_compute");



  const load = () => {

    getSectors().then(setSectors);

    Promise.all([getAlerts(activeSectorId), getGlobalAlerts()]).then(([sector, global]) => {

      const merged = [...global.items, ...sector.items];

      const seen = new Set<string>();

      setAlerts(

        merged.filter((a) => {

          const key = `${a.type}:${a.message}`;

          if (seen.has(key)) return false;

          seen.add(key);

          return true;

        })

      );

    });

    getHealth().then((h) => setComponents(h.components || {}));

    getDataAdapters().then((d) => setAdapters(d.items));

  };



  useEffect(() => {

    load();

  }, [activeSectorId]);



  const confirm = async (sector: Sector) => {

    if (reason.trim().length < 5) {

      message.warning("请填写确认理由（≥5字）");

      return;

    }

    setLoading(true);

    try {

      await confirmSector(sector.id, true, reason);

      message.success("赛道景气已确认（ConfirmSectorBeta）");

      setReason("");

      load();

    } catch (e: unknown) {

      const err = e as { response?: { data?: { detail?: string } } };

      message.error(err.response?.data?.detail || "确认失败");

    } finally {

      setLoading(false);

    }

  };



  const handleWatchlistSelect = (item: WatchlistItem) => {

    setAgentFocus(item.sector_name);

    if (item.sector_id) {

      setActiveSectorId(item.sector_id);

    }

  };



  const syncMetrics = async (adapter?: string) => {

    setSyncLoading(true);

    try {

      const r = await syncSectorMetrics(activeSectorId, adapter);

      message.success(`指标同步完成（${r.adapter}/${r.count} 条）`);

      load();

    } catch (e: unknown) {

      const err = e as { response?: { data?: { detail?: string } } };

      message.error(err.response?.data?.detail || "同步失败");

    } finally {

      setSyncLoading(false);

    }

  };



  return (

    <div>

      <Typography.Title level={3}>产业瓶颈 Alpha 智能选股系统</Typography.Title>

      <Typography.Paragraph type="secondary">

        动态观察清单驱动 Agent 扫描 → 研究员确认景气 → 图谱研判 → 候选入池 → 报告审核。

      </Typography.Paragraph>



      <Alert

        type="warning"

        showIcon

        style={{ marginBottom: 16 }}

        message="投研流程门控"

        description="智能体仅推荐 beta_candidate 提案；须研究员 ConfirmSectorBeta 确认后，方可生成候选池与 GraphRAG 报告。"

      />



      <WorkflowGuide />



      <WatchlistPanel

        focus={agentFocus}

        selectedSectorId={activeSectorId}

        onSelect={handleWatchlistSelect}

      />



      <Card size="small" title="Agent 运行参数" style={{ marginBottom: 16 }}>

        <Space direction="vertical" style={{ width: "100%" }}>

          <Input

            placeholder="关注方向（同步至动态观察清单 focus 源）"

            value={agentFocus}

            onChange={(e) => setAgentFocus(e.target.value)}

          />

          <Input.TextArea

            rows={2}

            placeholder="补充研究问题（可选）"

            value={agentQuery}

            onChange={(e) => setAgentQuery(e.target.value)}

          />

          <Typography.Text type="secondary">

            当前操作赛道：<Tag color="blue">{activeSectorId}</Tag>（点击观察清单行可切换）

          </Typography.Text>

        </Space>

      </Card>



      <AgentConsole

        sectorId={activeSectorId}

        focus={agentFocus}

        query={agentQuery}

        onFocusChange={setAgentFocus}

        onReload={load}

      />



      {alerts.length > 0 && (

        <Card size="small" title="Object Set 告警" style={{ marginBottom: 16 }}>

          <List

            size="small"

            dataSource={alerts}

            renderItem={(a) => (

              <List.Item>

                <Tag color={a.level === "high" ? "red" : a.level === "medium" ? "orange" : "blue"}>

                  {a.type}

                </Tag>

                {a.message}

              </List.Item>

            )}

          />

        </Card>

      )}



      <Card size="small" title="基础设施与数据适配器" style={{ marginBottom: 16 }}>

        <Space direction="vertical" style={{ width: "100%" }}>

          <Space wrap>

            {Object.entries(components).map(([k, v]) => {

              if (k === "data_adapters") return null;

              return (

                <Tag

                  key={k}

                  color={v === true || v === "neo4j" ? "green" : typeof v === "object" ? "blue" : "default"}

                >

                  {k}: {typeof v === "object" ? JSON.stringify(v) : String(v)}

                </Tag>

              );

            })}

          </Space>

          <Space wrap>

            {adapters.map((a) => (

              <Tag key={a.name} color={a.mode === "live" ? "green" : "default"}>

                {a.name}/{a.mode}

                {a.live_configured ? " ✓" : ""}

              </Tag>

            ))}

            <Button size="small" loading={syncLoading} onClick={() => syncMetrics("wind")}>

              Wind 同步指标

            </Button>

            <Button size="small" loading={syncLoading} onClick={() => syncMetrics()}>

              默认适配器同步

            </Button>

          </Space>

        </Space>

      </Card>



      <Row gutter={[16, 16]}>

        {sectors.map((s) => (

          <Col key={s.id} xs={24} lg={12}>

            <Card

              title={s.name}

              extra={statusTag(s)}

              actions={[

                <Link key="graph" to="/graph">产业图谱</Link>,

                <Link key="dash" to="/dashboard">产业看板</Link>,

                <Link key="cand" to="/candidates">候选池</Link>,

              ]}

            >

              <Space direction="vertical" style={{ width: "100%" }}>

                <Typography.Text>需求增速提示：{s.demand_growth_hint ?? "—"}%</Typography.Text>

                <Typography.Text type="secondary">赛道 ID：{s.id}</Typography.Text>

                {!(s.status === "beta_confirmed" && s.human_confirmed) && (

                  <>

                    <Input.TextArea

                      rows={2}

                      placeholder="确认理由（≥5字）"

                      value={reason}

                      onChange={(e) => setReason(e.target.value)}

                    />

                    <Button type="primary" loading={loading} onClick={() => confirm(s)}>

                      确认赛道景气

                    </Button>

                  </>

                )}

              </Space>

            </Card>

          </Col>

        ))}

      </Row>

    </div>

  );

}


