import { Card, Empty } from "antd";

export default function GraphPage() {
  return (
    <Card title="产业链拓扑（G6 画布待接入）">
      <Empty description="Neo4j 种子数据导入后，此处展示可交互产业图谱" />
    </Card>
  );
}
