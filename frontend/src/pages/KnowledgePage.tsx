import { useEffect, useState } from "react";
import {
  App as AntApp,
  Button,
  Card,
  Collapse,
  Descriptions,
  Form,
  Input,
  List,
  Modal,
  Space,
  Switch,
  Tag,
  Typography,
  Upload,
} from "antd";
import { InboxOutlined } from "@ant-design/icons";
import AgentWorkflowProgress from "../components/AgentWorkflowProgress";
import SectorConstituentConfigPanel from "../components/SectorConstituentConfigPanel";
import AgentPageStrip from "../components/agent-session/AgentPageStrip";
import {
  confirmKnowledgeDraft,
  getKnowledgeDrafts,
  getSectorWorkflowStatus,
  getUploadedDocuments,
  ingestKnowledgeAsync,
  ingestSectorReports,
  runKnowledgeIngestAgent,
  syncSectorConstituents,
  syncSectorReports,
  uploadResearchReport,
  validateKnowledgeDraft,
  type KnowledgeDraft,
  type KnowledgeDraftValidation,
  type SectorWorkflowStatus,
  type UploadedDocument,
} from "../lib/api";
import { useSector } from "../lib/sectorContext";

const SAMPLE = "磷化铟衬底是 EML光芯片 的上游，产能紧张扩产周期长达24个月，属于瓶颈环节。";

export default function KnowledgePage() {
  const { message, modal } = AntApp.useApp();
  const { sectorId } = useSector();
  const [form] = Form.useForm();
  const [drafts, setDrafts] = useState<KnowledgeDraft[]>([]);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [workflow, setWorkflow] = useState<SectorWorkflowStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extractOnUpload, setExtractOnUpload] = useState(true);
  const [uploadRef, setUploadRef] = useState("");
  const [reportLoading, setReportLoading] = useState(false);
  const [detailDraft, setDetailDraft] = useState<KnowledgeDraft | null>(null);
  const [validation, setValidation] = useState<KnowledgeDraftValidation | null>(null);
  const [validating, setValidating] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [lastBootstrap, setLastBootstrap] = useState<string | null>(null);

  const load = () => {
    if (!sectorId) return;
    getKnowledgeDrafts(sectorId).then((r) => setDrafts(r.items));
    getUploadedDocuments(sectorId).then(setDocuments);
    getSectorWorkflowStatus(sectorId).then(setWorkflow);
  };

  useEffect(() => {
    load();
  }, [sectorId]);

  useEffect(() => {
    form.setFieldsValue({ content: SAMPLE, source_ref: "示例-产业研报 2026Q1" });
  }, [form]);

  const hasConstituents = (workflow?.graph_stats.companies ?? 0) > 0;

  const submit = async (asyncMode: boolean) => {
    const vals = await form.validateFields();
    setLoading(true);
    try {
      if (asyncMode) {
        const r = await ingestKnowledgeAsync({
          sector_id: sectorId,
          source_type: "research_report",
          source_ref: vals.source_ref,
          content: vals.content,
        });
        message.success(
          r.mode === "celery" ? `已提交异步任务 ${r.task_id}` : `同步完成 ${r.draft_id}`
        );
      } else {
        await runKnowledgeIngestAgent({
          sector_id: sectorId,
          source_ref: vals.source_ref,
          content: vals.content,
        });
        message.success("Knowledge Agent 抽取完成，已生成草案");
      }
      load();
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const r = await uploadResearchReport(file, sectorId, uploadRef || undefined, extractOnUpload);
      message.success(`${r.message}（${r.chunk_count} 块已索引）`);
      if (r.draft_id) {
        message.info(`已同步生成知识草案 ${r.draft_id}`);
      }
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "上传失败");
    } finally {
      setUploading(false);
    }
    return false;
  };

  const openDetail = (draft: KnowledgeDraft) => {
    setDetailDraft(draft);
    setValidation(null);
  };

  const runValidate = async (draftId: string) => {
    setValidating(true);
    try {
      const result = await validateKnowledgeDraft(draftId);
      setValidation(result);
      if (result.can_confirm_all) {
        message.success("校验通过，可校准入库");
      } else {
        message.warning(`有 ${result.blocked_count} 条关系被 F5 规则阻断`);
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "校验失败");
    } finally {
      setValidating(false);
    }
  };

  const doConfirm = async (draftId: string, force: boolean) => {
    setConfirming(true);
    try {
      const r = await confirmKnowledgeDraft(draftId, force);
      message.success(force ? "已强制校准入库" : "草案已校准入库（CalibrateChain）");
      if (r.bootstrap) {
        const bs = r.bootstrap as { constituents?: { status?: string }; report_draft?: unknown };
        const stats = r.graph_stats_after as { products?: number; companies?: number } | undefined;
        setLastBootstrap(
          `Bootstrap：${stats?.products ?? "?"} 产品 · ${stats?.companies ?? "?"} 成分股` +
            (bs.constituents?.status === "skipped" ? "（成分股同步跳过）" : "")
        );
      }
      setDetailDraft(null);
      setValidation(null);
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "入库失败");
    } finally {
      setConfirming(false);
    }
  };

  const confirm = (draftId: string) => {
    if (validation?.draft_id === draftId && !validation.can_confirm_all) {
      modal.confirm({
        title: "强制校准入库？",
        content: `有 ${validation.blocked_count} 条关系未通过多源交叉校验。`,
        okText: "强制入库",
        okButtonProps: { danger: true },
        onOk: () => doConfirm(draftId, true),
      });
      return;
    }
    doConfirm(draftId, false);
  };

  const syncReports = async () => {
    if (!sectorId) return;
    setReportLoading(true);
    try {
      const r = await syncSectorReports(sectorId);
      message.success(r.message ?? `同步完成（${r.count ?? 0} 条）`);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "同步失败");
    } finally {
      setReportLoading(false);
    }
  };

  const ingestReports = async () => {
    if (!sectorId) return;
    setReportLoading(true);
    try {
      const r = await ingestSectorReports(sectorId);
      if (r.status === "empty") {
        message.info(r.message || "暂无研报可抽取");
      } else {
        message.success(`研报抽取完成 → 草案已生成`);
      }
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "抽取失败");
    } finally {
      setReportLoading(false);
    }
  };

  const syncConstituents = async () => {
    try {
      const r = await syncSectorConstituents(sectorId);
      message.success(r.message ?? "成分股同步已触发");
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "同步失败");
    }
  };

  const renderDraftDetail = () => {
    if (!detailDraft) return null;
    const ext = detailDraft.extracted;
    const rels = validation?.relations ?? ext.relations ?? [];
    const products = validation?.new_products ?? ext.new_products ?? [];

    return (
      <Modal
        open
        title={`草案 ${detailDraft.draft_id}`}
        width={720}
        onCancel={() => {
          setDetailDraft(null);
          setValidation(null);
        }}
        footer={
          detailDraft.status === "draft"
            ? [
                <Button key="v" loading={validating} onClick={() => runValidate(detailDraft.draft_id)}>
                  校验
                </Button>,
                <Button key="c" type="primary" loading={confirming} onClick={() => confirm(detailDraft.draft_id)}>
                  校准入库
                </Button>,
              ]
            : [<Button key="close" onClick={() => setDetailDraft(null)}>关闭</Button>]
        }
      >
        <Descriptions size="small" column={1} bordered style={{ marginBottom: 16 }}>
          <Descriptions.Item label="来源">{detailDraft.source_ref}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={detailDraft.status === "confirmed" ? "green" : "blue"}>{detailDraft.status}</Tag>
          </Descriptions.Item>
          {validation && (
            <Descriptions.Item label="校验结果">
              {validation.can_confirm_all ? (
                <Tag color="green">全部关系可确认</Tag>
              ) : (
                <Tag color="orange">阻断 {validation.blocked_count} 条关系</Tag>
              )}
            </Descriptions.Item>
          )}
        </Descriptions>
        {products.length > 0 && (
          <List
            size="small"
            header={`新产品节点 (${products.length})`}
            dataSource={products}
            renderItem={(p) => (
              <List.Item>
                <Tag color="purple">{p.product_id}</Tag> {p.name}
              </List.Item>
            )}
            style={{ marginBottom: 16 }}
          />
        )}
        {rels.length > 0 && (
          <List
            size="small"
            header="产业链关系"
            dataSource={rels}
            renderItem={(rel) => (
              <List.Item>
                {rel.source_name ?? rel.source_id} → {rel.target_name ?? rel.target_id}
              </List.Item>
            )}
          />
        )}
      </Modal>
    );
  };

  const pendingDrafts = drafts.filter((d) => d.status !== "confirmed");

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Typography.Title level={4}>证据与校准（阶段② 产业链构建）</Typography.Title>

      {workflow && (
        <Card size="small">
          <AgentWorkflowProgress
            phases={workflow.phases}
            currentPhase={workflow.current_phase}
            steps={workflow.steps}
            currentStep={workflow.current_step}
            compact
          />
        </Card>
      )}

      {lastBootstrap && (
        <Typography.Text type="success">{lastBootstrap}</Typography.Text>
      )}

      <Card title="Knowledge Agent — 上传 / 粘贴 → 草案 → 人工确认">
        <Typography.Paragraph type="secondary">
          主路径：文本或研报 → Knowledge Agent 抽取三元组 → 校验 → <strong>CalibrateChain</strong> 确认入库。
          确认后若图谱仍空将自动触发成分股 Bootstrap。
        </Typography.Paragraph>
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Input
            placeholder="来源标注（上传可选）"
            value={uploadRef}
            onChange={(e) => setUploadRef(e.target.value)}
          />
          <Space>
            <span>上传后自动抽取</span>
            <Switch checked={extractOnUpload} onChange={setExtractOnUpload} />
          </Space>
          <Upload.Dragger
            accept=".txt,.md,.pdf,.docx"
            multiple={false}
            showUploadList={false}
            beforeUpload={handleUpload}
            disabled={uploading}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">拖拽研报上传（TXT/MD/PDF/DOCX）</p>
          </Upload.Dragger>
          <Form form={form} layout="vertical">
            <Form.Item name="source_ref" label="来源" rules={[{ required: true }]}>
              <Input placeholder="产业研报 2026Q1" />
            </Form.Item>
            <Form.Item name="content" label="粘贴文本" rules={[{ required: true, min: 20 }]}>
              <Input.TextArea rows={4} />
            </Form.Item>
            <Space>
              <Button type="primary" loading={loading} onClick={() => submit(false)}>
                运行 Knowledge Agent
              </Button>
              <Button loading={loading} onClick={() => submit(true)}>
                异步抽取
              </Button>
            </Space>
          </Form>
        </Space>
      </Card>

      <Card title={`待校准草案 (${pendingDrafts.length})`}>
        <List
          dataSource={drafts}
          locale={{ emptyText: "暂无草案，请上方运行 Knowledge Agent" }}
          renderItem={(d) => (
            <List.Item
              actions={
                d.status === "draft"
                  ? [
                      <a key="d" onClick={() => openDetail(d)}>详情 / 确认</a>,
                    ]
                  : [<Tag key="ok" color="green">已确认</Tag>]
              }
            >
              <List.Item.Meta
                title={
                  <Space>
                    <Tag>{d.draft_id}</Tag>
                    {d.source_ref}
                  </Space>
                }
                description={
                  <Typography.Text type="secondary">
                    产品 {d.extracted.new_products?.length ?? 0} · 关系 {d.extracted.relations?.length ?? 0}
                  </Typography.Text>
                }
              />
            </List.Item>
          )}
        />
      </Card>

      <Collapse
        defaultActiveKey={["constituent"]}
        items={[
          {
            key: "constituent",
            label: "成分股同步配置（东财板块 → 上市公司入图）",
            children: sectorId ? (
              <SectorConstituentConfigPanel sectorId={sectorId} compact />
            ) : (
              <Typography.Text type="secondary">请先选择赛道</Typography.Text>
            ),
          },
          {
            key: "enrich",
            label: "数据 enrichment（可选）— 东财研报元数据补充",
            children: (
              <Space direction="vertical" style={{ width: "100%" }}>
                <Typography.Paragraph type="secondary">
                  拓扑仍以 Agent 草案为准；东财同步用于补充 ODS 证据。请先配置上方成分股映射并同步成分股。
                </Typography.Paragraph>
                <Space wrap>
                  <Button
                    loading={reportLoading}
                    onClick={syncReports}
                    disabled={!hasConstituents}
                  >
                    同步研报元数据（em）
                  </Button>
                  <Button
                    type="default"
                    loading={reportLoading}
                    onClick={ingestReports}
                    disabled={!hasConstituents}
                  >
                    研报标题 → 抽取草案
                  </Button>
                  <Button onClick={syncConstituents}>同步成分股</Button>
                </Space>
                {!hasConstituents && (
                  <Typography.Text type="warning" style={{ fontSize: 12 }}>
                    尚无成分股：请先在上方配置东财板块并保存，再点「同步成分股」。
                  </Typography.Text>
                )}
                <List
                  size="small"
                  header="已入库研报"
                  dataSource={documents}
                  locale={{ emptyText: "暂无上传研报" }}
                  renderItem={(d) => (
                    <List.Item>
                      <Tag>{d.doc_id}</Tag> {d.filename} · {d.chunk_count} 块
                    </List.Item>
                  )}
                />
              </Space>
            ),
          },
        ]}
      />

      {renderDraftDetail()}

      <AgentPageStrip
        sectorId={sectorId}
        focus="knowledge"
        workflowStep={2}
        pageHint="本页 Agent：上传研报、抽取知识、确认草稿"
        onReload={load}
      />
    </Space>
  );
}
