import { Select, Space, Typography } from "antd";
import { useSector } from "../lib/sectorContext";

export default function SectorSelect() {
  const { sectorId, setSectorId, sectors } = useSector();
  return (
    <Space size={4}>
      <Typography.Text style={{ color: "rgba(255,255,255,0.65)", whiteSpace: "nowrap" }}>
        当前赛道
      </Typography.Text>
      <Select
        size="small"
        value={sectorId || undefined}
        style={{ width: 180 }}
        placeholder={sectors.length ? "选择赛道" : "暂无赛道"}
        notFoundContent="请先采纳赛道推荐"
        options={sectors.map((s) => ({ value: s.id, label: s.name }))}
        onChange={setSectorId}
      />
    </Space>
  );
}
