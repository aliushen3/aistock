import { useEffect, useState } from "react";
import {
  App as AntApp,
  Button,
  Form,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import {
  getSectorConstituentConfig,
  importSectorConstituentSeed,
  saveSectorConstituentConfig,
  type ConstituentBoardEntry,
  type SectorConstituentConfigMeta,
} from "../lib/api";

interface Props {
  sectorId: string;
  compact?: boolean;
}

export default function SectorConstituentConfigPanel({ sectorId, compact }: Props) {
  const { message } = AntApp.useApp();
  const [form] = Form.useForm();
  const [meta, setMeta] = useState<SectorConstituentConfigMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = () => {
    if (!sectorId) return;
    setLoading(true);
    getSectorConstituentConfig(sectorId)
      .then((m) => {
        setMeta(m);
        form.setFieldsValue({
          boards: m.config.boards?.length ? m.config.boards : [{ type: "concept", name: "" }],
          default_product_id: m.config.default_product_id,
          product_keywords: Object.fromEntries(
            Object.entries(m.config.product_keywords || {}).map(([pid, kws]) => [
              pid,
              Array.isArray(kws) ? kws.join(", ") : kws,
            ])
          ),
        });
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [sectorId]);

  const save = async () => {
    const vals = await form.validateFields();
    setSaving(true);
    try {
      const boards = (vals.boards as ConstituentBoardEntry[]).filter((b) => b?.name?.trim());
      const keywords = vals.product_keywords || {};
      const cleaned: Record<string, string[]> = {};
      for (const [pid, kws] of Object.entries(keywords)) {
        const arr = Array.isArray(kws)
          ? kws
          : String(kws || "")
              .split(/[,，]/)
              .map((s) => s.trim())
              .filter(Boolean);
        if (arr.length) cleaned[pid] = arr;
      }
      const r = await saveSectorConstituentConfig(sectorId, {
        boards,
        default_product_id: vals.default_product_id || null,
        product_keywords: cleaned,
      });
      setMeta(r);
      message.success("成分股配置已保存到 Sector");
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const importSeed = async () => {
    try {
      const r = await importSectorConstituentSeed(sectorId);
      setMeta(r);
      load();
      message.success("已从内置种子导入");
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail ?? "导入失败");
    }
  };

  const sourceTag =
    meta?.source === "db" ? (
      <Tag color="green">已存 DB</Tag>
    ) : meta?.source === "json_seed" ? (
      <Tag color="blue">内置种子</Tag>
    ) : (
      <Tag color="orange">未配置</Tag>
    );

  const products = meta?.available_products ?? [];

  return (
    <div>
      <Space style={{ marginBottom: 8 }} wrap>
        {sourceTag}
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          东财板块 → 成分股入图；关键词映射公司到 Product 节点
        </Typography.Text>
      </Space>
      <Form form={form} layout="vertical" disabled={loading || !sectorId}>
        <Form.List name="boards">
          {(fields, { add, remove }) => (
            <>
              <Typography.Text strong>东财板块</Typography.Text>
              {fields.map(({ key, name, ...rest }) => (
                <Space key={key} align="baseline" style={{ display: "flex", marginBottom: 8 }}>
                  <Form.Item {...rest} name={[name, "type"]} initialValue="concept">
                    <Select
                      style={{ width: 100 }}
                      options={[
                        { value: "concept", label: "概念" },
                        { value: "industry", label: "行业" },
                      ]}
                    />
                  </Form.Item>
                  <Form.Item
                    {...rest}
                    name={[name, "name"]}
                    rules={[{ required: true, message: "板块名称" }]}
                    style={{ flex: 1, minWidth: 200 }}
                  >
                    <Input placeholder="如 氟化工概念 / CPO概念" />
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(name)} />
                </Space>
              ))}
              <Button type="dashed" onClick={() => add({ type: "concept", name: "" })} icon={<PlusOutlined />}>
                添加板块
              </Button>
            </>
          )}
        </Form.List>

        <Form.Item name="default_product_id" label="默认 Product（无关键词匹配时）" style={{ marginTop: 16 }}>
          <Select
            allowClear
            placeholder="选择默认环节"
            options={products.map((p) => ({ value: p.id, label: `${p.name} (${p.id})` }))}
          />
        </Form.Item>

        {!compact && products.length > 0 && (
          <>
            <Typography.Text strong>公司名 → Product 关键词</Typography.Text>
            <Table
              size="small"
              pagination={false}
              style={{ marginTop: 8, marginBottom: 16 }}
              rowKey="id"
              dataSource={products}
              columns={[
                { title: "Product", dataIndex: "name", width: 140 },
                { title: "ID", dataIndex: "id", width: 160, ellipsis: true },
                {
                  title: "关键词（逗号分隔）",
                  render: (_: unknown, p: { id: string }) => (
                    <Form.Item name={["product_keywords", p.id]} noStyle>
                      <Input placeholder="巨化, 三美, PVDF" />
                    </Form.Item>
                  ),
                },
              ]}
            />
          </>
        )}

        <Space wrap>
          <Button type="primary" loading={saving} onClick={save}>
            保存配置
          </Button>
          {meta?.source !== "db" && (
            <Button onClick={importSeed}>从内置种子导入</Button>
          )}
        </Space>
      </Form>
    </div>
  );
}
