import type { AgentRunSummary, IntentResponse, UIBlock } from "../../lib/api";

export type StreamEventHandler = {
  onIntent?: (intent: IntentResponse) => void;
  onMessageDelta?: (content: string) => void;
  onMessageDone?: () => void;
  onSummaryDelta?: (content: string) => void;
  onSummaryDone?: () => void;
  onAgentStart?: (agentKey: string) => void;
  onStepStart?: (step: string) => void;
  onStepDone?: (data: { step: string; status: string }) => void;
  onBlock?: (block: UIBlock) => void;
  onRunComplete?: (result: AgentRunSummary) => void;
  onSession?: (sessionId: string) => void;
  onNavigate?: (route: string) => void;
  onDone?: () => void;
  onError?: (detail: string) => void;
};

export interface SessionStreamRequest {
  session_id?: string;
  message: string;
  sector_id?: string;
  focus?: string;
  workflow_step?: number;
  recent_messages?: string[];
  use_llm?: boolean;
  stream_assistant?: boolean;
  operator?: string;
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  return { event, data };
}

/** 消费 POST SSE 流（fetch + ReadableStream） */
export async function consumeAgentSessionStream(
  body: SessionStreamRequest,
  handlers: StreamEventHandler
): Promise<void> {
  const resp = await fetch("/api/v1/agents/session/message/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "X-Operator": body.operator || "analyst",
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.text();
    handlers.onError?.(err || `HTTP ${resp.status}`);
    return;
  }
  const reader = resp.body?.getReader();
  if (!reader) {
    handlers.onError?.("无响应流");
    return;
  }
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const parsed = parseSseBlock(part.trim());
      if (!parsed) continue;
      try {
        const payload = JSON.parse(parsed.data);
        switch (parsed.event) {
          case "intent":
            handlers.onIntent?.(payload as IntentResponse);
            break;
          case "message_delta":
            handlers.onMessageDelta?.(payload.content as string);
            break;
          case "message_done":
            handlers.onMessageDone?.();
            break;
          case "summary_delta":
            handlers.onSummaryDelta?.(payload.content as string);
            break;
          case "summary_done":
            handlers.onSummaryDone?.();
            break;
          case "agent_start":
            handlers.onAgentStart?.(payload.agent_key as string);
            break;
          case "step_start":
            handlers.onStepStart?.(payload.step as string);
            break;
          case "step_done":
            handlers.onStepDone?.(payload as { step: string; status: string });
            break;
          case "block":
            handlers.onBlock?.(payload as UIBlock);
            break;
          case "run_complete":
            handlers.onRunComplete?.(payload as AgentRunSummary);
            break;
          case "session":
            handlers.onSession?.(payload.session_id as string);
            break;
          case "done":
            if (payload.navigate) handlers.onNavigate?.(payload.navigate as string);
            handlers.onDone?.();
            break;
          case "error":
            handlers.onError?.((payload.detail as string) || "流式错误");
            break;
          default:
            break;
        }
      } catch {
        /* ignore malformed chunk */
      }
    }
  }
  handlers.onDone?.();
}
