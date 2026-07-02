import { Space, Tag } from "antd";

interface Props {
  chips: string[];
  onSelect: (chip: string) => void;
  disabled?: boolean;
}

export default function AgentIntentChips({ chips, onSelect, disabled }: Props) {
  if (!chips.length) return null;
  return (
    <Space wrap size={[4, 4]} style={{ marginBottom: 8 }}>
      {chips.map((c) => (
        <Tag
          key={c}
          style={{ cursor: disabled ? "not-allowed" : "pointer" }}
          onClick={() => !disabled && onSelect(c)}
        >
          {c}
        </Tag>
      ))}
    </Space>
  );
}
