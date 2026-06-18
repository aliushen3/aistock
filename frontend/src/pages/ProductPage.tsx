import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  App as AntApp,
  Button,
  Card,
  Descriptions,
  Input,
  List,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import {
  executeOntologyAction,
  getProductHintScore,
  type Citation,
} from "../lib/api";

interface HintScoreData {
  product_id: string;
  product_name: string;
  hint_score: number;
  hint_level: string;
  breakdown: Record<string, number>;
  hit_rules: string[];
  bottleneck_status: string;
  human_confirmed: boolean;
  evidence: Citation[];
  note: string;
}

const statusColor: Record<string, string> = {
  bottleneck_confirmed: "red",
  bottleneck_hint: "orange",
  none: "default",
};

export default function ProductPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const [data, setData] = useState<HintScoreData | null>(null);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    if (!productId) return;
    setLoading(true);
    getProductHintScore(productId)
      .then(setData)
      .finally(() => setLoading(false));
  };

  useEffect(load, [productId]);

  const confirmBottleneck = async () => {
    if (!productId || !data) return;
    if (reason.trim().length < 3) {
      message.warning("请填写确认理由");
      return;
    }
    setSubmitting(true);
    try {
      await executeOntologyAction(
        "ConfirmBottleneck",
        { type: "Product", id: productId },
        { reason },
        "analyst"
      );
      message.success("瓶颈环节已确认（ConfirmBottleneck Action）");
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } | string } } };
      const detail = err.response?.data?.detail;
      const msg = typeof detail === "object" ? detail?.message : detail;
      message.error(msg || "确认失败");
    } finally {
      setSubmitting(false);
    }
  };

  if (!productId) return null;

  return (
    <Card
      title="产品详情"
      extra={
        <Button type="link" onClick={() => navigate("/graph")}>
          返回图谱
        </Button>
      }
    >
      <Spin spinning={loading}>
        {data && (
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="产品 ID">{data.product_id}</Descriptions.Item>
              <Descriptions.Item label="名称">{data.product_name}</Descriptions.Item>
              <Descriptions.Item label="瓶颈状态">
                <Tag color={statusColor[data.bottleneck_status] ?? "default"}>
                  {data.bottleneck_status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="提示分">
                <Typography.Text strong>{data.hint_score}</Typography.Text>（{data.hint_level}）
              </Descriptions.Item>
              <Descriptions.Item label="人工确认">
                {data.human_confirmed ? <Tag color="green">是</Tag> : <Tag>否</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="命中规则">
                {data.hit_rules.join("、") || "—"}
              </Descriptions.Item>
            </Descriptions>

            <Typography.Title level={5}>提示分拆解</Typography.Title>
            <Descriptions bordered size="small" column={2}>
              {Object.entries(data.breakdown).map(([k, v]) => (
                <Descriptions.Item key={k} label={k}>
                  {v}
                </Descriptions.Item>
              ))}
            </Descriptions>

            <Typography.Title level={5}>证据引用</Typography.Title>
            <List
              size="small"
              bordered
              dataSource={data.evidence}
              locale={{ emptyText: "暂无证据" }}
              renderItem={(e) => (
                <List.Item>
                  <Typography.Text strong>[{e.ref_id}]</Typography.Text>&nbsp;
                  <Tag>{e.source_type}</Tag> {e.source_ref} — {e.excerpt}
                </List.Item>
              )}
            />

            {data.bottleneck_status === "bottleneck_hint" && (
              <Card size="small" title="人工确认瓶颈（ConfirmBottleneck Action）" type="inner">
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Input.TextArea
                    rows={2}
                    placeholder="确认理由（必填）"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                  <Button type="primary" loading={submitting} onClick={confirmBottleneck}>
                    确认瓶颈环节
                  </Button>
                  <Typography.Text type="secondary">
                    需研究员权限；执行后同步 Neo4j 投影（若可用）。
                  </Typography.Text>
                </Space>
              </Card>
            )}

            <Typography.Text type="secondary">{data.note}</Typography.Text>
          </Space>
        )}
      </Spin>
    </Card>
  );
}
