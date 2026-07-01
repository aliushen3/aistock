import { Collapse, Steps, Typography } from "antd";
import { Link } from "react-router-dom";

const STEPS = [
  {
    title: "① 发现景气赛道",
    description: (
      <>
        一键扫描（按主力资金 + 多日涨幅 + 题材热度排序），或按<strong>关注方向</strong>扫描；也可先在
        <Link to="/knowledge"> 知识抽取 </Link>
        上传研报补强证据。采纳推荐后，研究员确认景气。
      </>
    ),
  },
  {
    title: "② 研判产业",
    description: (
      <>
        <Link to="/dashboard">产业看板</Link> 看景气指标，
        <Link to="/graph">产业图谱</Link> 找卡脖子环节与受益路径。
      </>
    ),
  },
  {
    title: "③ 筛选标的",
    description: (
      <>
        <Link to="/candidates">候选池</Link> 看多逻辑融合标的，
        <Link to="/diagnosis">智能诊断</Link> 过滤散户陷阱。
      </>
    ),
  },
  {
    title: "④ 论证成文",
    description: (
      <>
        <Link to="/report">投研报告</Link> 自动生成初稿，人工审核后发布。
      </>
    ),
  },
  {
    title: "⑤ 确认入池",
    description: (
      <>
        回候选池勾选标的、写明理由 → <strong>人工入池</strong>（<Link to="/audit">审计日志</Link> 全程留痕）。
      </>
    ),
  },
];

export default function WorkflowGuide() {
  return (
    <Collapse
      style={{ marginBottom: 16 }}
      items={[
        {
          key: "guide",
          label: "投研流程指引（5 步，点击展开）",
          children: (
            <>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
                上传研报是<strong>知识增强</strong>，不替代研判；系统评分仅供排序，不构成投资建议。
              </Typography.Paragraph>
              <Steps direction="vertical" size="small" current={-1} items={STEPS} />
            </>
          ),
        },
      ]}
    />
  );
}
