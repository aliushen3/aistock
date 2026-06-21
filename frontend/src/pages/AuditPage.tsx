import { useEffect, useState } from "react";
import { Card, Table, Tag, Typography } from "antd";
import { getAuditLog, getPendingReviews, type AuditEntry } from "../lib/api";

export default function AuditPage() {
  const [items, setItems] = useState<AuditEntry[]>([]);
  const [pending, setPending] = useState<{ pending_id: string; action_type: string; target_id: string; first_operator: string }[]>([]);

  useEffect(() => {
    getAuditLog().then((r) => setItems(r.items));
    getPendingReviews().then((r) => setPending(r.items));
  }, []);

  return (
    <Card title="审计日志（人工操作留痕）">
      <Typography.Paragraph type="secondary">
        记录赛道确认、瓶颈确认、入池、报告发布等 Ontology Action，合规保留 ≥3 年。
      </Typography.Paragraph>
      {pending.length > 0 && (
        <Card size="small" title="待双人复核" style={{ marginBottom: 16 }}>
          <Table
            size="small"
            pagination={false}
            rowKey="pending_id"
            dataSource={pending}
            columns={[
              { title: "ID", dataIndex: "pending_id" },
              { title: "Action", dataIndex: "action_type", render: (v: string) => <Tag>{v}</Tag> },
              { title: "目标", dataIndex: "target_id" },
              { title: "发起人", dataIndex: "first_operator" },
            ]}
          />
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
            render: (v: string | undefined, r: AuditEntry) => v || "—",
          },
        ]}
      />
    </Card>
  );
}
