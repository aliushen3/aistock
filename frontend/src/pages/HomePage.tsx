import { Card, Col, Row, Typography } from "antd";

const docs = [
  { title: "系统定位", desc: "定性投研辅助，量化仅作提示" },
  { title: "双逻辑融合", desc: "买方产业 Alpha + Serenity 逆向" },
  { title: "知识工程", desc: "本体、图谱、溯源、专家校准" },
  { title: "人机协同", desc: "机器起草，人工定稿入池" },
];

export default function HomePage() {
  return (
    <div>
      <Typography.Title level={3}>产业瓶颈 Alpha 智能选股系统</Typography.Title>
      <Typography.Paragraph type="secondary">
        一期 MVP 聚焦 AI 算力赛道，跑通图谱 → 候选 → 报告 → 人工入池闭环。
      </Typography.Paragraph>
      <Row gutter={[16, 16]}>
        {docs.map((d) => (
          <Col key={d.title} xs={24} sm={12} lg={6}>
            <Card title={d.title}>{d.desc}</Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
