import { useEffect, useState } from "react";
import { Alert, Card, Table, Tag, Typography } from "antd";
import { getDiagnosis, type DiagnosisItem } from "../lib/api";

const SECTOR = "sector_ai_compute";

const verdictColor: Record<string, string> = {
  retail_trap: "red",
  professional_alpha: "green",
  mixed: "orange",
};

export default function DiagnosisPage() {
  const [items, setItems] = useState<DiagnosisItem[]>([]);

  useEffect(() => {
    getDiagnosis(SECTOR).then((r) => setItems(r.items));
  }, []);

  return (
    <Card title="散户 vs 专业模式智能诊断">
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="区分题材炒作（散户陷阱）与产业壁垒 Alpha（专业主升）"
      />
      <Table
        size="small"
        rowKey="stock_code"
        dataSource={items}
        pagination={false}
        columns={[
          { title: "代码", dataIndex: "stock_code", width: 90 },
          { title: "名称", dataIndex: "name" },
          {
            title: "诊断",
            dataIndex: "verdict_label",
            render: (_: string, r: DiagnosisItem) => (
              <Tag color={verdictColor[r.verdict]}>{r.verdict_label}</Tag>
            ),
          },
          { title: "散户分", dataIndex: "retail_score", width: 80 },
          { title: "专业分", dataIndex: "professional_score", width: 80 },
          { title: "建议", dataIndex: "advice", ellipsis: true },
        ]}
        expandable={{
          expandedRowRender: (r) => (
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {r.signals.map((s, i) => (
                <li key={i}>
                  <Tag color={s.type === "retail" ? "red" : "green"}>{s.signal}</Tag> {s.detail}
                </li>
              ))}
            </ul>
          ),
        }}
      />
      <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
        诊断结果仅供投研参考，不构成投资建议
      </Typography.Paragraph>
    </Card>
  );
}
