import { Collapse, Steps, Typography } from "antd";
import { Link } from "react-router-dom";

/** 五阶段上手引导 — 与后端呈现模型一致：赛道 → 产业链 → 环节 → 标的 → 跟踪 */
const STEPS = [
  {
    title: "① 赛道确认",
    description: (
      <>
        在 Agent 会话输入「发现景气赛道」（可带关注方向），在结果面板采纳推荐并
        <strong>确认景气</strong>。确认后可「一键投研」自动推进后续阶段。
      </>
    ),
  },
  {
    title: "② 产业链构建",
    description: (
      <>
        Agent 自动抽取产业拓扑；你在<Link to="/knowledge">证据与校准</Link>
        审核知识草案、上传研报补强证据、同步成分股。
      </>
    ),
  },
  {
    title: "③ 环节挖掘",
    description: (
      <>
        瓶颈扫描与 Serenity 逆向溯源<strong>并行</strong>产出提案；在
        <Link to="/graph">产业研究</Link>图谱上核对并确认关键环节。
      </>
    ),
  },
  {
    title: "④ 标的论证与入池",
    description: (
      <>
        在<Link to="/candidates">标的论证</Link>逐个查看多空对照与三道闸（预期差 / 价值捕获 / 反证），
        回应空头论点后入池；<Link to="/report">研究报告</Link>为论证产出物，审核后发布。
      </>
    ),
  },
  {
    title: "⑤ 持续跟踪",
    description: (
      <>
        <Link to="/dashboard">组合跟踪</Link>监控正式池标的的逻辑健康度（保鲜 / 瓶颈缓解 / 空头应验），
        告警自动回到决策收件箱。
      </>
    ),
  },
];

export default function WorkflowGuide() {
  return (
    <Collapse
      style={{ marginBottom: 16 }}
      defaultActiveKey={["guide"]}
      items={[
        {
          key: "guide",
          label: "投研五阶段上手指引（Agent 推进，人做裁决）",
          children: (
            <>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
                Agent 负责扫描、起草、对抗与告警；你负责确认、否决与担责。
                系统评分仅供排序，不构成投资建议。
              </Typography.Paragraph>
              <Steps direction="vertical" size="small" current={-1} items={STEPS} />
            </>
          ),
        },
      ]}
    />
  );
}
