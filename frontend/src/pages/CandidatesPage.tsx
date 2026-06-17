import { Button, Card, Space, Table, Tag } from "antd";

const columns = [
  { title: "代码", dataIndex: "code" },
  { title: "名称", dataIndex: "name" },
  { title: "模式", dataIndex: "mode", render: (v: string) => <Tag>{v}</Tag> },
  { title: "提示分", dataIndex: "hint" },
  {
    title: "状态",
    dataIndex: "status",
    render: () => <Tag color="orange">待确认</Tag>,
  },
  {
    title: "操作",
    render: () => (
      <Space>
        <Button type="primary" size="small">
          确认入池
        </Button>
        <Button size="small" danger>
          否决
        </Button>
      </Space>
    ),
  },
];

export default function CandidatesPage() {
  return (
    <Card title="候选池（须人工确认后方可入正式池）">
      <Table columns={columns} dataSource={[]} locale={{ emptyText: "暂无候选" }} rowKey="code" />
    </Card>
  );
}
