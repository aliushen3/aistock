import { Alert, Button, Empty, Space, Typography } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { syncSectorConstituents } from "../lib/api";

interface Props {
  step?: number;
  sectorId?: string;
  stats?: { products: number; companies: number; drafts?: number };
  gated?: boolean;
  gateMessage?: string;
  onSyncConstituents?: () => void;
}

export default function WorkflowEmptyGuide({
  step = 2,
  sectorId,
  stats,
  gated,
  gateMessage,
  onSyncConstituents,
}: Props) {
  const navigate = useNavigate();

  const sync = async () => {
    if (!sectorId) return;
    if (onSyncConstituents) {
      onSyncConstituents();
      return;
    }
    await syncSectorConstituents(sectorId);
  };

  return (
    <Empty
      description={
        <Space direction="vertical" size="small">
          {gated && gateMessage && (
            <Alert type="warning" showIcon message={gateMessage} style={{ textAlign: "left" }} />
          )}
          <Typography.Text>
            {step === 2 && "产业拓扑尚未构建。请通过 Knowledge Agent 上传/粘贴研报生成草案并确认。"}
            {step === 3 && "图谱为空或无瓶颈数据。请先完成 Step 2 或运行瓶颈扫描 Agent。"}
            {step >= 4 && "看板数据不足。请同步成分股与 ODS 指标，或在知识页构建拓扑。"}
          </Typography.Text>
          {stats && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              当前：{stats.products} 产品 · {stats.companies} 成分股
              {typeof stats.drafts === "number" ? ` · ${stats.drafts} 待校准草案` : ""}
            </Typography.Text>
          )}
        </Space>
      }
    >
      <Space wrap>
        <Button type="primary" onClick={() => navigate("/knowledge")}>
          去知识抽取
        </Button>
        {sectorId && stats && stats.companies === 0 && (
          <Button onClick={sync}>同步成分股</Button>
        )}
        <Link to="/">返回工作台</Link>
      </Space>
    </Empty>
  );
}
