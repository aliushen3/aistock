import { Card, Steps, Typography } from "antd";
import { Link } from "react-router-dom";

const STEPS = [
  {
    title: "① 发现赛道",
    description: (
      <>
        首页查看<strong>动态观察清单</strong>，运行<strong>赛道推荐智能体</strong>，或先在
        <Link to="/knowledge"> 知识抽取 </Link>
        上传研报补强证据 → 采纳推荐 → 确认赛道景气
      </>
    ),
  },
  {
    title: "② 研判产业",
    description: (
      <>
        <Link to="/dashboard">产业看板</Link> 看指标，
        <Link to="/graph">产业图谱</Link> 看瓶颈与 Serenity 路径
      </>
    ),
  },
  {
    title: "③ 筛选标的",
    description: (
      <>
        <Link to="/candidates">候选池</Link> 查看双逻辑融合标的，
        <Link to="/diagnosis">智能诊断</Link> 过滤散户陷阱
      </>
    ),
  },
  {
    title: "④ 论证报告",
    description: (
      <>
        <Link to="/report">投研报告</Link> 生成 GraphRAG 草稿 → 人工审核发布
      </>
    ),
  },
  {
    title: "⑤ 确认入池",
    description: (
      <>
        回到候选池勾选标的、填写理由 → <strong>人工入池</strong>（<Link to="/audit">审计日志</Link> 留痕）
      </>
    ),
  },
];

export default function WorkflowGuide() {
  return (
    <Card title="投研流程指引（5 步上手）" size="small" style={{ marginBottom: 16 }}>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
        上传研报只是<strong>知识增强</strong>，不替代研判。提示分仅供排序，不构成投资建议。
      </Typography.Paragraph>
      <Steps direction="vertical" size="small" current={-1} items={STEPS} />
    </Card>
  );
}
