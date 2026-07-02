import { Input, Space, Button } from "antd";
import { SendOutlined } from "@ant-design/icons";
import { useState } from "react";

interface Props {
  onSend: (text: string) => void;
  loading?: boolean;
  placeholder?: string;
}

export default function AgentChatInput({ onSend, loading, placeholder }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    if (!text.trim()) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <Space.Compact style={{ width: "100%" }}>
      <Input.TextArea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder || "描述投研意图，Enter 发送，Shift+Enter 换行"}
        autoSize={{ minRows: 2, maxRows: 6 }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        disabled={loading}
      />
      <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={submit}>
        发送
      </Button>
    </Space.Compact>
  );
}
