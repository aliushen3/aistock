import { List, Typography } from "antd";
import type { AgentMessage } from "./useAgentSession";

interface Props {
  messages: AgentMessage[];
}

export default function AgentMessageList({ messages }: Props) {
  return (
    <List
      size="small"
      dataSource={messages}
      style={{ maxHeight: 360, overflow: "auto", marginBottom: 12 }}
      renderItem={(m) => (
        <List.Item style={{ border: "none", padding: "6px 0" }}>
          <div style={{ width: "100%" }}>
            <Typography.Text
              type={m.role === "user" ? undefined : m.role === "system" ? "secondary" : undefined}
              strong={m.role === "user"}
              style={{ fontSize: 12, color: m.role === "assistant" ? "#1677ff" : undefined }}
            >
              {m.role === "user" ? "你" : m.role === "system" ? "系统" : "Agent"}
            </Typography.Text>
            <Typography.Paragraph style={{ marginBottom: 0, marginTop: 4, whiteSpace: "pre-wrap" }}>
              {m.content}
              {m.streaming && <Typography.Text type="secondary">▍</Typography.Text>}
            </Typography.Paragraph>
          </div>
        </List.Item>
      )}
    />
  );
}
