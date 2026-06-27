import { useEffect, useState } from "react";
import {
  App as AntApp,
  Button,
  Card,
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
import {
  confirmKnowledgeDraft,
  getKnowledgeDrafts,
  getUploadedDocuments,
  ingestKnowledge,
  ingestKnowledgeAsync,
  ingestSectorReports,
  syncSectorReports,
  uploadResearchReport,
  validateKnowledgeDraft,
  type KnowledgeDraft,
  type KnowledgeDraftValidation,
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
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extractOnUpload, setExtractOnUpload] = useState(true);
  const [uploadRef, setUploadRef] = useState("");
  const [reportLoading, setReportLoading] = useState(false);
  const [detailDraft, setDetailDraft] = useState<KnowledgeDraft | null>(null);
  const [validation, setValidation] = useState<KnowledgeDraftValidation | null>(null);
  const [validating, setValidating] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const load = () => {
    if (!sectorId) return;
    getKnowledgeDrafts(sectorId).then((r) => setDrafts(r.items));
    getUploadedDocuments(sectorId).then(setDocuments);
  };

  useEffect(() => {
    load();
  }, [sectorId]);

  useEffect(() => {
    form.setFieldsValue({ content: SAMPLE, source_ref: "示例-产业研报 2026Q1" });
  }, [form]);

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
        await ingestKnowledge({
          sector_id: sectorId,
          source_type: "research_report",
          source_ref: vals.source_ref,
          content: vals.content,
        });
        message.success("知识抽取完成，已生成草案");
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
        message.warning(`有 ${result.blocked_count} 条关系被 F5 规则阻断，需 force 确认或补充硬源`);
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
      await confirmKnowledgeDraft(draftId, force);
      message.success(force ? "已强制校准入库" : "草案已校准入库");
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
        content: (
          <Typography.Paragraph>
            有 {validation.blocked_count} 条关系未通过多源交叉校验（单一研报来源）。
            强制确认将跳过 F5 阻断规则，请确认已人工复核。
          </Typography.Paragraph>
        ),
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
      message.success(
        r.status === "skipped"
          ? `未启用 ODS，已跳过（拉取 ${r.count ?? 0} 条）`
          : `研报元数据同步完成（${r.adapter ?? "-"}/${r.count ?? 0} 条）`
      );
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
        message.info("暂无研报标题可抽取，请先同步研报元数据");
      } else {
        message.success(`研报抽取完成：${r.bottleneck_hints ?? 0} 条瓶颈提示 → 已生成草案`);
      }
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "抽取失败");
    } finally {
      setReportLoading(false);
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
                <Button
                  key="c"
                  type="primary"
                  loading={confirming}
                  onClick={() => confirm(detailDraft.draft_id)}
                >
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
              {validation.note && (
                <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                  {validation.note}
                </Typography.Text>
              )}
            </Descriptions.Item>
          )}
        </Descriptions>

        {products.length > 0 && (
          <>
            <Typography.Title level={5}>新产品节点 ({products.length})</Typography.Title>
            <List
              size="small"
              dataSource={products}
              renderItem={(p) => (
                <List.Item>
                  <Space wrap>
                    <Tag color="purple">{p.product_id}</Tag>
                    <span>{p.name}</span>
                    {p.layer && <Tag>{p.layer}</Tag>}
                    {p.already_exists && <Tag color="default">已存在</Tag>}
                    {p.is_new && !p.already_exists && <Tag color="cyan">待创建</Tag>}
                  </Space>
                </List.Item>
              )}
              style={{ marginBottom: 16 }}
            />
          </>
        )}

        {(rels.length > 0 || (ext.relations?.length ?? 0) > 0) && (
          <>
            <Typography.Title level={5}>产业链关系</Typography.Title>
            <List
              size="small"
              dataSource={rels}
              renderItem={(rel) => (
                <List.Item>
                  <Space direction="vertical" size={0}>
                    <span>
                      {rel.source_name ?? rel.source_id} → {rel.target_name ?? rel.target_id}
                    </span>
                    {rel.validation && (
                      <Space size={4}>
                        {rel.validation.can_confirm ? (
                          <Tag color="green">可确认</Tag>
                        ) : (
                          <Tag color="red">阻断{rel.validation.report_only ? "（仅研报）" : ""}</Tag>
                        )}
                      </Space>
                    )}
                  </Space>
                </List.Item>
              )}
              style={{ marginBottom: 16 }}
            />
          </>
        )}

        {(ext.bottleneck_hints?.length ?? 0) > 0 && (
          <>
            <Typography.Title level={5}>瓶颈提示</Typography.Title>
            <List
              size="small"
              dataSource={ext.bottleneck_hints ?? []}
              renderItem={(h) => (
                <List.Item>
                  {h.product_name ?? h.product_id}
                  {h.confidence && <Tag style={{ marginLeft: 8 }}>{h.confidence}</Tag>}
                </List.Item>
              )}
            />
          </>
        )}

        {ext.evidence_excerpt && (
          <>
            <Typography.Title level={5}>证据摘录</Typography.Title>
            <Typography.Paragraph type="secondary">{ext.evidence_excerpt}</Typography.Paragraph>
          </>
        )}
      </Modal>
    );
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="外部研报数据源（东方财富，免费）">
        <Typography.Paragraph type="secondary">
          先同步研报元数据到 ODS，再从标题抽取产能/扩产瓶颈信号生成知识草案（草案见下方「待校准草案」）。
        </Typography.Paragraph>
        <Space wrap>
          <Button loading={reportLoading} onClick={syncReports}>
            同步研报元数据（em）
          </Button>
          <Button type="primary" loading={reportLoading} onClick={ingestReports}>
            研报标题 → 抽取草案
          </Button>
        </Space>
      </Card>

      <Card title="外部研报上传（替代 API 接入）">
        <Typography.Paragraph type="secondary">
          支持 TXT / MD / PDF / DOCX，原文归档至 MinIO，正文分块写入 Qdrant 向量库，可选同步知识抽取。
        </Typography.Paragraph>
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Input
            placeholder="来源标注（可选，默认取文件名）"
            value={uploadRef}
            onChange={(e) => setUploadRef(e.target.value)}
          />
          <Space>
            <span>上传后知识抽取</span>
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
            <p className="ant-upload-text">点击或拖拽研报文件到此处上传</p>
            <p className="ant-upload-hint">单文件 ≤ 20MB</p>
          </Upload.Dragger>
        </Space>
      </Card>

      <Card title="已入库研报">
        <List
          dataSource={documents}
          locale={{ emptyText: "暂无上传研报" }}
          renderItem={(d) => (
            <List.Item>
              <List.Item.Meta
                title={
                  <Space>
                    <Tag>{d.doc_id}</Tag>
                    {d.source_ref}
                  </Space>
                }
                description={
                  <Typography.Text type="secondary">
                    {d.filename} · {d.char_count} 字 · {d.chunk_count} 块 · {d.status}
                  </Typography.Text>
                }
              />
            </List.Item>
          )}
        />
      </Card>

      <Card title="知识抽取（文本粘贴 → 草案三元组）">
        <Form form={form} layout="vertical">
          <Form.Item name="source_ref" label="来源" rules={[{ required: true }]}>
            <Input placeholder="示例-产业研报 2026Q1" />
          </Form.Item>
          <Form.Item name="content" label="文本内容" rules={[{ required: true, min: 20 }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          <Space>
            <Button type="primary" loading={loading} onClick={() => submit(false)}>
              同步抽取
            </Button>
            <Button loading={loading} onClick={() => submit(true)}>
              异步抽取（Celery + MinIO）
            </Button>
          </Space>
        </Form>
      </Card>

      <Card title="待校准草案">
        <List
          dataSource={drafts}
          locale={{ emptyText: "暂无草案" }}
          renderItem={(d) => (
            <List.Item
              actions={
                d.status === "draft"
                  ? [
                      <a key="d" onClick={() => openDetail(d)}>详情</a>,
                      <a key="c" onClick={() => openDetail(d)}>校准入库</a>,
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
                    新产品 {(d.extracted.new_products?.length ?? 0)} 个 · 关系{" "}
                    {d.extracted.relations?.length ?? 0} 条 · 瓶颈提示{" "}
                    {d.extracted.bottleneck_hints?.length ?? 0} 条
                  </Typography.Text>
                }
              />
            </List.Item>
          )}
        />
      </Card>

      {renderDraftDetail()}
    </Space>
  );
}
