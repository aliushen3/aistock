import { useEffect, useState } from "react";
import {
  App as AntApp,
  Button,
  Card,
  Form,
  Input,
  List,
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
  uploadResearchReport,
  type KnowledgeDraft,
  type UploadedDocument,
} from "../lib/api";

const SECTOR = "sector_ai_compute";

const SAMPLE = "磷化铟衬底是 EML光芯片 的上游，产能紧张扩产周期长达24个月，属于瓶颈环节。";

export default function KnowledgePage() {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const [drafts, setDrafts] = useState<KnowledgeDraft[]>([]);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extractOnUpload, setExtractOnUpload] = useState(true);
  const [uploadRef, setUploadRef] = useState("");

  const load = () => {
    getKnowledgeDrafts(SECTOR).then((r) => setDrafts(r.items));
    getUploadedDocuments(SECTOR).then(setDocuments);
  };

  useEffect(() => {
    load();
    form.setFieldsValue({ content: SAMPLE, source_ref: "示例-产业研报 2026Q1" });
  }, [form]);

  const submit = async (asyncMode: boolean) => {
    const vals = await form.validateFields();
    setLoading(true);
    try {
      if (asyncMode) {
        const r = await ingestKnowledgeAsync({
          sector_id: SECTOR,
          source_type: "research_report",
          source_ref: vals.source_ref,
          content: vals.content,
        });
        message.success(
          r.mode === "celery" ? `已提交异步任务 ${r.task_id}` : `同步完成 ${r.draft_id}`
        );
      } else {
        await ingestKnowledge({
          sector_id: SECTOR,
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
      const r = await uploadResearchReport(file, SECTOR, uploadRef || undefined, extractOnUpload);
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

  const confirm = async (draftId: string) => {
    await confirmKnowledgeDraft(draftId);
    message.success("草案已校准入库");
    load();
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
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
                  ? [<a key="c" onClick={() => confirm(d.draft_id)}>校准入库</a>]
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
                    关系 {d.extracted.relations?.length ?? 0} 条 · 瓶颈提示{" "}
                    {d.extracted.bottleneck_hints?.length ?? 0} 条
                  </Typography.Text>
                }
              />
            </List.Item>
          )}
        />
      </Card>
    </Space>
  );
}
