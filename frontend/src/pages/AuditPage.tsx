import { useEffect, useState } from "react";
import { App as AntApp, Button, Card, Input, Modal, Space, Table, Tag, Typography } from "antd";
import {
  approvePendingReview,
  getAuditLog,
  getPendingReviews,
  rejectPendingReview,
  type AuditEntry,
  type PendingReview,
} from "../lib/api";
import { useUser } from "../lib/userContext";

export default function AuditPage() {
  const { message } = AntApp.useApp();
  const { operator } = useUser();
  const [items, setItems] = useState<AuditEntry[]>([]);
  const [pending, setPending] = useState<PendingReview[]>([]);
  const [acting, setActing] = useState<string | null>(null);

  const load = () => {
    getAuditLog().then((r) => setItems(r.items));
    getPendingReviews().then((r) => setPending(r.items));
  };

  useEffect(load, []);

  const approve = async (p: PendingReview) => {
    setActing(p.pending_id);
    try {
      const r = await approvePendingReview(p.pending_id, operator);
      message.success(r.message ?? "复核通过，Action 已生效");
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } | string } } };
      const detail = err.response?.data?.detail;
      message.error(typeof detail === "string" ? detail : detail?.message ?? "复核失败");
    } finally {
      setActing(null);
    }
  };

  const reject = (p: PendingReview) => {
    let reason = "";
    Modal.confirm({
      title: `驳回 ${p.action_type}`,
      content: (
        <Input.TextArea
          rows={3}
          placeholder="驳回理由（将写入审计日志）"
          onChange={(e) => (reason = e.target.value)}
        />
      ),
      onOk: async () => {
        try {
          await rejectPendingReview(p.pending_id, operator, reason);
          message.success("已驳回，原 Action 不生效");
          load();
        } catch (e: unknown) {
          const err = e as { response?: { data?: { detail?: string } } };
          message.error(err.response?.data?.detail ?? "驳回失败");
          throw e;
        }
      },
    });
  };

  return (
    <Card title="审计日志（人工操作留痕）">
      <Typography.Paragraph type="secondary">
        记录赛道确认、瓶颈确认、入池、报告发布等 Ontology Action，合规保留 ≥3 年。
        高风险操作须双人复核：第二人（须与发起人不同）在下方通过或驳回。
      </Typography.Paragraph>
      {pending.length > 0 && (
        <Card size="small" title={`待双人复核（${pending.length}）`} style={{ marginBottom: 16 }}>
          <Table
            size="small"
            pagination={false}
            rowKey="pending_id"
            dataSource={pending}
            columns={[
              { title: "ID", dataIndex: "pending_id", width: 140 },
              { title: "Action", dataIndex: "action_type", render: (v: string) => <Tag>{v}</Tag> },
              { title: "目标", dataIndex: "target_id" },
              { title: "发起人", dataIndex: "first_operator", width: 110 },
              {
                title: "复核操作",
                width: 190,
                render: (_: unknown, p: PendingReview) => {
                  const sameOperator = p.first_operator === operator;
                  return (
                    <Space>
                      <Button
                        size="small"
                        type="primary"
                        loading={acting === p.pending_id}
                        disabled={sameOperator}
                        title={sameOperator ? "双人复核须由不同操作者执行" : undefined}
                        onClick={() => approve(p)}
                      >
                        复核通过
                      </Button>
                      <Button size="small" danger disabled={sameOperator} onClick={() => reject(p)}>
                        驳回
                      </Button>
                    </Space>
                  );
                },
              },
            ]}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            当前操作者：<Tag>{operator}</Tag>发起人与复核人相同时按钮禁用（可在右上角切换操作者）。
          </Typography.Text>
        </Card>
      )}
      <Table
        size="small"
        rowKey="id"
        dataSource={items}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: "ID", dataIndex: "id", width: 60 },
          { title: "操作", dataIndex: "action", render: (v: string) => <Tag>{v}</Tag> },
          { title: "操作者", dataIndex: "operator", width: 100 },
          { title: "目标", dataIndex: "target" },
          {
            title: "时间",
            dataIndex: "created_at",
            width: 180,
            render: (v: string | undefined) => v || "—",
          },
        ]}
      />
    </Card>
  );
}
