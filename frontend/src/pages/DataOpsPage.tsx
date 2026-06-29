import { useEffect, useState } from "react";
import { App as AntApp, Button, Card, Col, Descriptions, Row, Space, Statistic, Table, Tag, Typography } from "antd";
import { useSector } from "../lib/sectorContext";
import {
  fetchSevenLayerData,
  getDataAdapters,
  getHealth,
  getOdsStats,
  getSevenLayerCapabilities,
  ingestSectorReports,
  runDataSourcePipeline,
  runDataSourceFetchAgent,
  syncSectorAnnouncements,
  syncSectorConstituents,
  syncSectorFinancials,
  syncSectorMarket,
  syncSectorMetrics,
  syncSectorReports,
  syncSevenLayerToOds,
  type DataAdapterInfo,
  type OdsStats,
  type SevenLayerCapability,
} from "../lib/api";

interface SyncResult {
  adapter?: string;
  count?: number;
  status?: string;
  companies_upserted?: number;
  demo_removed?: number;
  links_created?: number;
}

const KIND_LABEL: Record<string, string> = {
  market: "行情",
  announcement: "公告",
  metrics: "材料行情",
  financial: "财报",
  research: "研报",
  constituent: "成分股",
};

export default function DataOpsPage() {
  const { message } = AntApp.useApp();
  const { sectorId } = useSector();
  const [components, setComponents] = useState<Record<string, unknown>>({});
  const [adapters, setAdapters] = useState<DataAdapterInfo[]>([]);
  const [odsStats, setOdsStats] = useState<OdsStats | null>(null);
  const [sevenLayers, setSevenLayers] = useState<SevenLayerCapability[]>([]);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [previewLayer, setPreviewLayer] = useState<string | null>(null);

  const load = () => {
    getHealth().then((h) => setComponents(h.components || {}));
    getDataAdapters().then((d) => setAdapters(d.items));
    getOdsStats().then(setOdsStats);
    getSevenLayerCapabilities().then((d) => setSevenLayers(d.items));
  };

  useEffect(() => {
    load();
  }, []);

  const runSync = async (key: string, label: string, fn: () => Promise<SyncResult>) => {
    if (!sectorId) {
      message.warning("请先在右上角选择赛道");
      return;
    }
    setBusyKey(key);
    try {
      const r = await fn();
      if (r.status === "skipped") {
        message.info(`${label}：未启用 ODS，已跳过（拉取 ${r.count ?? 0} 条）`);
      } else if (r.companies_upserted != null) {
        message.success(
          `${label}完成（写入 ${r.companies_upserted} 家，移除演示 ${r.demo_removed ?? 0} 家，产品链接 ${r.links_created ?? 0} 条）`
        );
      } else {
        message.success(`${label}完成（来源 ${r.adapter ?? "-"}，写入 ${r.count ?? 0} 条）`);
      }
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || `${label}失败`);
    } finally {
      setBusyKey(null);
      getOdsStats().then(setOdsStats);
    }
  };

  const syncActions: { key: string; label: string; fn: () => Promise<SyncResult> }[] = [
    { key: "constituents", label: "同步成分股", fn: () => syncSectorConstituents(sectorId) },
    { key: "market", label: "同步行情", fn: () => syncSectorMarket(sectorId) },
    { key: "announcements", label: "同步公告", fn: () => syncSectorAnnouncements(sectorId) },
    { key: "financials", label: "同步财报", fn: () => syncSectorFinancials(sectorId) },
    { key: "metrics", label: "同步材料行情", fn: () => syncSectorMetrics(sectorId) },
    { key: "reports", label: "同步研报元数据", fn: () => syncSectorReports(sectorId) },
    { key: "ingest", label: "研报标题抽取草案", fn: () => ingestSectorReports(sectorId) },
  ];

  const previewLayerData = async (layer: string) => {
    setPreviewLayer(layer);
    try {
      const data = await fetchSevenLayerData({ layer, limit: 5 });
      const keys = Object.keys(data).slice(0, 4).join(", ");
      message.success(`${layer} 层预览成功（字段: ${keys}）`);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || "预览失败");
    } finally {
      setPreviewLayer(null);
    }
  };

  const runAgentFetch = async (task: string) => {
    setBusyKey(`agent-${task}`);
    try {
      const r = await runDataSourceFetchAgent({
        task,
        sector_id: sectorId || undefined,
        limit: 10,
      });
      message.success(r.agent_summary || "数据源智能体执行完成");
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || "智能体执行失败");
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div>
      <Typography.Title level={3}>系统与数据</Typography.Title>
      <Typography.Paragraph type="secondary">
        数据源采集与基础设施状态，面向管理员 / 数据运维。采集结果写入本地 ODS，业务页面仅读取本地库。
      </Typography.Paragraph>

      <Card
        size="small"
        title="A 股七层数据架构"
        style={{ marginBottom: 16 }}
        extra={<Tag color="blue">{sevenLayers.length} 层 · stockdata skill</Tag>}
      >
        <Table
          size="small"
          rowKey="layer"
          pagination={false}
          dataSource={sevenLayers}
          columns={[
            { title: "层", dataIndex: "layer", width: 120 },
            { title: "名称", dataIndex: "label", width: 100 },
            {
              title: "数据源",
              dataIndex: "sources",
              render: (v: string[]) => v.map((s) => <Tag key={s}>{s}</Tag>),
            },
            {
              title: "ODS",
              dataIndex: "ods_ready",
              width: 80,
              render: (v: boolean) => (v ? <Tag color="green">就绪</Tag> : <Tag>预览</Tag>),
            },
            {
              title: "操作",
              width: 180,
              render: (_: unknown, row: SevenLayerCapability) => (
                <Space>
                  <Button
                    size="small"
                    loading={previewLayer === row.layer}
                    onClick={() => previewLayerData(row.layer)}
                  >
                    预览
                  </Button>
                  {row.ods_ready && sectorId && (
                    <Button
                      size="small"
                      disabled={busyKey === `ods-${row.layer}`}
                      loading={busyKey === `ods-${row.layer}`}
                      onClick={() =>
                        runSync(`ods-${row.layer}`, `${row.label} ODS`, () =>
                          syncSevenLayerToOds({ layer: row.layer, sector_id: sectorId })
                        )
                      }
                    >
                      同步 ODS
                    </Button>
                  )}
                </Space>
              ),
            },
          ]}
        />
        <Space wrap style={{ marginTop: 12 }}>
          <Typography.Text type="secondary">数据源 Pipeline：</Typography.Text>
          <Button
            type="primary"
            loading={busyKey === "pipeline-full"}
            disabled={!sectorId}
            onClick={async () => {
              if (!sectorId) return;
              setBusyKey("pipeline-full");
              try {
                const r = await runDataSourcePipeline({ sector_id: sectorId, preset: "full_collection" });
                message.success(r.agent_summary || "Pipeline 完成");
              } catch (e: unknown) {
                const err = e as { response?: { data?: { detail?: string } } };
                message.error(err.response?.data?.detail || "Pipeline 失败");
              } finally {
                setBusyKey(null);
                load();
              }
            }}
          >
            全量采集 Pipeline
          </Button>
          <Button
            loading={busyKey === "pipeline-ods"}
            disabled={!sectorId}
            onClick={async () => {
              if (!sectorId) return;
              setBusyKey("pipeline-ods");
              try {
                const r = await runDataSourcePipeline({ sector_id: sectorId, preset: "ods_warmup" });
                message.success(r.agent_summary || "ODS 同步完成");
              } catch (e: unknown) {
                const err = e as { response?: { data?: { detail?: string } } };
                message.error(err.response?.data?.detail || "ODS Pipeline 失败");
              } finally {
                setBusyKey(null);
                load();
              }
            }}
          >
            ODS 四层入库
          </Button>
        </Space>
        <Space wrap style={{ marginTop: 12 }}>
          <Typography.Text type="secondary">单任务智能体：</Typography.Text>
          <Button loading={busyKey === "agent-sector_scan"} onClick={() => runAgentFetch("sector_scan")}>
            赛道扫描
          </Button>
          <Button loading={busyKey === "agent-signal"} onClick={() => runAgentFetch("signal")}>
            信号层
          </Button>
          <Button loading={busyKey === "agent-news"} onClick={() => runAgentFetch("news")}>
            新闻层
          </Button>
        </Space>
      </Card>

      <Card
        size="small"
        title="ODS 入库统计"
        style={{ marginBottom: 16 }}
        extra={
          odsStats ? (
            odsStats.enabled ? (
              <Tag color="green">ODS 已启用</Tag>
            ) : (
              <Tag color="orange">ODS 未启用</Tag>
            )
          ) : null
        }
      >
        {odsStats?.enabled ? (
          <Row gutter={[16, 16]}>
            {(
              [
                ["market_daily", "行情日线"],
                ["announcements", "公告"],
                ["financials", "财报"],
                ["industry_metrics", "材料行情"],
                ["external_reports", "研报元数据"],
                ["research_reports", "研报正文"],
              ] as const
            ).map(([key, label]) => (
              <Col key={key} xs={12} sm={8} md={4}>
                <Statistic title={label} value={odsStats[key] ?? 0} />
              </Col>
            ))}
          </Row>
        ) : (
          <Typography.Text type="secondary">
            未启用 ODS（ODS_ENABLED=false），采集结果不落库。配置数据库并启用后此处显示各表条数。
          </Typography.Text>
        )}
        {odsStats?.ontology_companies?.enabled && (
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={8}>
              <Statistic title="图谱公司总数" value={odsStats.ontology_companies.total ?? 0} />
            </Col>
            <Col xs={8}>
              <Statistic title="真实 A 股代码" value={odsStats.ontology_companies.real_codes ?? 0} />
            </Col>
            <Col xs={8}>
              <Statistic title="演示代码" value={odsStats.ontology_companies.demo_codes ?? 0} />
            </Col>
          </Row>
        )}
      </Card>

      <Card size="small" title="数据采集" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Typography.Text type="secondary">
            当前赛道：<Tag color="blue">{sectorId || "未选择"}</Tag>（在右上角切换）。
            生产环境建议由定时任务自动采集，此处仅供手动补采 / 验证。
          </Typography.Text>
          <Space wrap>
            {syncActions.map((a) => (
              <Button
                key={a.key}
                loading={busyKey === a.key}
                disabled={!sectorId}
                onClick={() => runSync(a.key, a.label, a.fn)}
              >
                {a.label}
              </Button>
            ))}
          </Space>
        </Space>
      </Card>

      <Card size="small" title="数据源状态" style={{ marginBottom: 16 }}>
        <Table
          size="small"
          rowKey={(r) => `${r.kind ?? "x"}:${r.name}`}
          pagination={false}
          dataSource={adapters}
          columns={[
            {
              title: "数据类型",
              dataIndex: "kind",
              width: 120,
              render: (v: string | undefined) => (v ? KIND_LABEL[v] ?? v : "—"),
            },
            { title: "数据源", dataIndex: "name", width: 160 },
            {
              title: "运行模式",
              dataIndex: "mode",
              width: 120,
              render: (v: string) =>
                v === "live" ? <Tag color="green">真实源</Tag> : <Tag>演示桩</Tag>,
            },
            {
              title: "默认",
              dataIndex: "default",
              width: 80,
              render: (v: boolean) => (v ? <Tag color="blue">默认</Tag> : "—"),
            },
            {
              title: "凭据就绪",
              dataIndex: "live_configured",
              render: (v: boolean) => (v ? <Tag color="green">已配置</Tag> : <Tag>未配置</Tag>),
            },
          ]}
        />
      </Card>

      <Card size="small" title="基础设施状态">
        <Descriptions size="small" column={1} bordered>
          {Object.entries(components)
            .filter(([k]) => k !== "data_adapters" && k !== "seven_layer")
            .map(([k, v]) => (
              <Descriptions.Item key={k} label={k}>
                <Tag color={v === true || v === "neo4j" ? "green" : typeof v === "object" ? "blue" : "default"}>
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </Tag>
              </Descriptions.Item>
            ))}
        </Descriptions>
      </Card>
    </div>
  );
}
