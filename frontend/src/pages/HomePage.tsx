import { useEffect, useState } from "react";
import {
  App as AntApp,
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  List,
  Row,
  Space,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { useNavigate } from "react-router-dom";
import AgentConsole from "../components/AgentConsole";
import WatchlistPanel from "../components/WatchlistPanel";
import WorkflowGuide from "../components/WorkflowGuide";
import { useSector } from "../lib/sectorContext";
import {
  confirmSector,
  getAlerts,
  getGlobalAlerts,
  getSectorRecommendations,
  getSectors,
  type AlertItem,
  type Sector,
  type SectorRecommendation,
  type WatchlistItem,
} from "../lib/api";

const isConfirmed = (s: Sector) => s.status === "beta_confirmed" && s.human_confirmed;

const statusTag = (s: Sector) => {
  if (isConfirmed(s)) return <Tag color="green">已确认景气</Tag>;
  if (s.status === "rejected") return <Tag color="red">已驳回</Tag>;
  return <Tag color="orange">待确认</Tag>;
};

export default function HomePage() {
  const { message } = AntApp.useApp();
  const navigate = useNavigate();
  const { sectorId: activeSectorId, setSectorId: setActiveSectorId, reloadSectors } = useSector();
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [recs, setRecs] = useState<SectorRecommendation[]>([]);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [agentFocus, setAgentFocus] = useState("AI算力");
  const [agentQuery, setAgentQuery] = useState("");

  const load = () => {
    getSectors().then(setSectors);
    reloadSectors();
    getSectorRecommendations().then(setRecs);
    if (!activeSectorId) {
      setAlerts([]);
      return;
    }
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
  };

  useEffect(() => {
    load();
  }, [activeSectorId]);

  const recBySector = (id: string) =>
    recs.find((r) => r.sector_id === id) || undefined;

  const setReason = (id: string, value: string) =>
    setReasons((prev) => ({ ...prev, [id]: value }));

  const confirm = async (sector: Sector) => {
    const reason = (reasons[sector.id] || "").trim();
    if (reason.length < 5) {
      message.warning("请填写确认理由（≥5字），将写入审计留痕");
      return;
    }
    setLoadingId(sector.id);
    try {
      await confirmSector(sector.id, true, reason);
      message.success(`已确认「${sector.name}」赛道景气`);
      setReason(sector.id, "");
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || "确认失败");
    } finally {
      setLoadingId(null);
    }
  };

  const handleWatchlistSelect = (item: WatchlistItem) => {
    setAgentFocus(item.sector_name);
    if (item.sector_id) {
      setActiveSectorId(item.sector_id);
    }
  };

  const pending = sectors.filter((s) => !isConfirmed(s) && s.status !== "rejected");
  const settled = sectors.filter((s) => isConfirmed(s) || s.status === "rejected");
  const activeSectorName = sectors.find((s) => s.id === activeSectorId)?.name;

  const evidence = (s: Sector) => {
    const rec = recBySector(s.id);
    return (
      <Space direction="vertical" size={4} style={{ width: "100%" }}>
        <Space wrap size={4}>
          <Tag>需求增速 {s.demand_growth_hint ?? "—"}%</Tag>
          {rec && <Tag color="purple">beta {rec.beta_score?.toFixed?.(2) ?? rec.beta_score}</Tag>}
          {rec?.signals?.demand_growth_ok && <Tag color="green">需求达标</Tag>}
          {rec?.signals?.capex_positive && <Tag color="green">资本开支正向</Tag>}
          {typeof rec?.signals?.research_support_count === "number" && (
            <Tag color="blue">研报支撑 {rec.signals.research_support_count}</Tag>
          )}
        </Space>
        {rec?.terminal_products?.length ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            终端产品：{rec.terminal_products.slice(0, 5).join("、")}
          </Typography.Text>
        ) : null}
        {rec?.rationale ? (
          <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 0 }} ellipsis={{ rows: 3, tooltip: rec.rationale }}>
            推荐依据：{rec.rationale}
          </Typography.Paragraph>
        ) : (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            暂无智能体推荐证据，请结合产业看板 / 图谱自行研判后确认。
          </Typography.Text>
        )}
        {rec?.risks?.length ? (
          <Typography.Text type="warning" style={{ fontSize: 12 }}>
            风险：{rec.risks.slice(0, 3).join("；")}
          </Typography.Text>
        ) : null}
      </Space>
    );
  };

  const goto = (s: Sector, path: string) => {
    setActiveSectorId(s.id);
    navigate(path);
  };

  const cardActions = (s: Sector) => [
    <a key="graph" onClick={() => goto(s, "/graph")}>产业图谱</a>,
    <a key="dash" onClick={() => goto(s, "/dashboard")}>产业看板</a>,
    <a key="cand" onClick={() => goto(s, "/candidates")}>候选池</a>,
  ];

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 4 }}>投研工作台</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        发现景气赛道 → 研究员确认 → 产业研判 → 候选入池 → 报告审核。系统只做排序打分，
        <Typography.Text strong>投研决策由你把关</Typography.Text>；评分仅供参考，不构成投资建议。
      </Typography.Paragraph>

      {sectors.length === 0 && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="从这里开始：三步发现你的第一个赛道"
          description={
            <>
              ① 在下方 <strong>「发现景气赛道」</strong> 一键扫描（按主力资金 + 多日涨幅 + 题材热度排序）→
              ② 从推荐里点 <strong>「采纳」</strong> 建立赛道 →
              ③ 在 <strong>「待确认赛道」</strong> 填写理由并确认景气，即可解锁候选池与投研报告。
            </>
          }
        />
      )}

      <WorkflowGuide />

      <WatchlistPanel
        focus={agentFocus}
        selectedSectorId={activeSectorId}
        onSelect={handleWatchlistSelect}
      />

      <Card size="small" title="观察焦点" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input
            placeholder="你想研究的方向，如 AI算力 / 固态电池 / 机器人（留空则按全市场资金与题材扫描）"
            value={agentFocus}
            onChange={(e) => setAgentFocus(e.target.value)}
            allowClear
          />
          <Input.TextArea
            rows={2}
            placeholder="补充研究问题（可选），如「关注光模块环节的国产替代进度」"
            value={agentQuery}
            onChange={(e) => setAgentQuery(e.target.value)}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            当前研究赛道：<Tag color="blue">{activeSectorName || "未选择"}</Tag>
            可在右上角切换，或点击下方观察清单某行快速切换。
          </Typography.Text>
        </Space>
      </Card>

      <AgentConsole
        sectorId={activeSectorId}
        sectorName={activeSectorName}
        focus={agentFocus}
        query={agentQuery}
        onFocusChange={setAgentFocus}
        onReload={load}
      />

      {alerts.length > 0 && (
        <Card size="small" title="系统告警" style={{ marginBottom: 16 }}>
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

      <Typography.Title level={4} style={{ marginTop: 8 }}>
        待确认赛道
        <Tooltip title="确认景气前请查看下方证据：需求增速、beta 信号、研报支撑、风险提示。理由将写入审计日志。">
          <Typography.Text type="secondary" style={{ fontSize: 13, marginLeft: 8, fontWeight: 400 }}>
            （确认后才解锁候选池与报告）
          </Typography.Text>
        </Tooltip>
      </Typography.Title>
      {pending.length === 0 ? (
        <Empty description="暂无待确认赛道，请在上方运行赛道扫描或采纳推荐" style={{ marginBottom: 16 }} />
      ) : (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          {pending.map((s) => (
            <Col key={s.id} xs={24} lg={12}>
              <Card title={s.name} extra={statusTag(s)} actions={cardActions(s)}>
                <Space direction="vertical" style={{ width: "100%" }}>
                  {evidence(s)}
                  <Input.TextArea
                    rows={2}
                    placeholder="确认理由（≥5字，写入审计）"
                    value={reasons[s.id] || ""}
                    onChange={(e) => setReason(s.id, e.target.value)}
                  />
                  <Button
                    type="primary"
                    block
                    loading={loadingId === s.id}
                    onClick={() => confirm(s)}
                  >
                    确认赛道景气
                  </Button>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {settled.length > 0 && (
        <>
          <Typography.Title level={4}>已处理赛道</Typography.Title>
          <Row gutter={[16, 16]}>
            {settled.map((s) => (
              <Col key={s.id} xs={24} lg={12}>
                <Card title={s.name} extra={statusTag(s)} actions={cardActions(s)}>
                  <Space direction="vertical" size={4} style={{ width: "100%" }}>
                    <Typography.Text>需求增速提示：{s.demand_growth_hint ?? "—"}%</Typography.Text>
                    {isConfirmed(s) ? (
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        已确认景气，可在候选池 / 报告中继续研判。
                      </Typography.Text>
                    ) : (
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        已驳回，不进入后续流程。
                      </Typography.Text>
                    )}
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </>
      )}
    </div>
  );
}
