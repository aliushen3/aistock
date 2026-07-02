import { Select, Space, Typography } from "antd";
import { useUser, type UserOperator } from "../lib/userContext";

const OPTIONS: { value: UserOperator; label: string }[] = [
  { value: "analyst", label: "研究员" },
  { value: "fund_manager", label: "基金经理" },
  { value: "risk", label: "风控" },
  { value: "data_admin", label: "数据管理员" },
  { value: "admin", label: "管理员" },
];

export default function OperatorSelect() {
  const { operator, setOperator } = useUser();
  return (
    <Space size={4}>
      <Typography.Text style={{ color: "rgba(255,255,255,0.65)", whiteSpace: "nowrap" }}>
        角色
      </Typography.Text>
      <Select
        size="small"
        value={operator}
        style={{ width: 110 }}
        options={OPTIONS}
        onChange={(v) => setOperator(v as UserOperator)}
      />
    </Space>
  );
}
