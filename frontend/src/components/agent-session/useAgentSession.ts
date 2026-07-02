import { useCallback, useEffect, useRef, useState } from "react";
import { App as AntApp } from "antd";
import {
  adoptSectorRecommendation,
  confirmSector,
  confirmSerenityRecommendation,
  createAgentSession,
  dismissBottleneckRecommendation,
  dismissSectorRecommendation,
  dismissSerenityRecommendation,
  getAgentSession,
  rebutBearCase,
  syncSectorConstituents,
  updateAgentSession,
  type AlertItem,
  type SectorWorkflowStatus,
  type UIBlock,
  type WorkflowTodo,
} from "../../lib/api";
import {
  buildPendingTodosBlock,
  buildWorkflowProgressBlock,
  fetchProposalBlocks,
  mergeUiBlocks,
} from "./proposalBlocks";
import { filterBlocksByOperator } from "../../lib/blockPermissions";
import { getStoredOperator } from "../../lib/operatorStorage";
import { useUser } from "../../lib/userContext";
import { consumeAgentSessionStream } from "./streamAgentSession";

export interface AgentMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  streaming?: boolean;
}

interface SessionContext {
  sectorId?: string;
  focus?: string;
  workflowStep?: number;
  workflowStatus?: SectorWorkflowStatus | null;
  onNavigate?: (path: string) => void;
  pendingTodos?: WorkflowTodo[];
  alerts?: AlertItem[];
  resumeSteps?: string[];
}

const SESSION_KEY = "aistock_agent_session_id";

const DEFAULT_WELCOME =
  "描述投研意图，例如「发现景气赛道」「从断点继续」「扫描瓶颈」。结构化结果将在结果抽屉（GUI）中展示与确认。";

let _msgSeq = 0;
function nextId() {
  _msgSeq += 1;
  return `msg_${_msgSeq}`;
}

export function useAgentSession(ctx: SessionContext, onReload?: () => void) {
  const { message } = AntApp.useApp();
  const { operator } = useUser();
  const [messages, setMessages] = useState<AgentMessage[]>([
    { id: nextId(), role: "assistant", content: DEFAULT_WELCOME, timestamp: Date.now() },
  ]);
  const [uiBlocks, setUiBlocks] = useState<UIBlock[]>([]);
  const [chips, setChips] = useState<string[]>(["发现景气赛道", "从断点继续", "扫描瓶颈"]);
  const [running, setRunning] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const proposalRef = useRef<UIBlock[]>([]);
  const messagesRef = useRef(messages);
  const uiBlocksRef = useRef(uiBlocks);
  const chipsRef = useRef(chips);
  const sessionIdRef = useRef<string | null>(null);

  messagesRef.current = messages;
  uiBlocksRef.current = uiBlocks;
  chipsRef.current = chips;
  sessionIdRef.current = sessionId;

  const appendMessage = (role: AgentMessage["role"], content: string, streaming = false) => {
    const id = nextId();
    setMessages((prev) => [...prev, { id, role, content, timestamp: Date.now(), streaming }]);
    return id;
  };

  const patchMessage = (id: string, patch: Partial<AgentMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  };

  const pendingBlock = buildPendingTodosBlock(
    ctx.pendingTodos ?? [],
    ctx.alerts ?? [],
    ctx.resumeSteps
  );
  const workflowBlock = buildWorkflowProgressBlock(ctx.workflowStatus);

  const applyMergedBlocks = useCallback(
    (agentBlocks: UIBlock[]) => {
      const merged = mergeUiBlocks(agentBlocks, proposalRef.current, pendingBlock, workflowBlock);
      setUiBlocks(filterBlocksByOperator(merged, operator));
    },
    [pendingBlock, workflowBlock, operator]
  );

  const reloadProposals = useCallback(async () => {
    proposalRef.current = await fetchProposalBlocks(ctx.sectorId);
    setUiBlocks((prev) =>
      filterBlocksByOperator(
        mergeUiBlocks(
          prev.filter((b) => !b.block_id.startsWith("proposal_") && b.block_id !== "context_workflow_progress"),
          proposalRef.current,
          pendingBlock,
          workflowBlock
        ),
        operator
      )
    );
  }, [ctx.sectorId, pendingBlock, workflowBlock, operator]);

  const persistSession = useCallback(async () => {
    const sid = sessionIdRef.current;
    if (!sid) return;
    try {
      await updateAgentSession(sid, {
        sector_id: ctx.sectorId,
        focus: ctx.focus,
        workflow_step: ctx.workflowStep,
        messages: messagesRef.current.map(({ id, role, content, timestamp }) => ({
          id,
          role,
          content,
          timestamp,
        })),
        ui_blocks: uiBlocksRef.current,
        chips: chipsRef.current,
      });
    } catch {
      /* 持久化失败不阻断交互 */
    }
  }, [ctx.sectorId, ctx.focus, ctx.workflowStep]);

  const ensureSession = useCallback(async () => {
    if (sessionIdRef.current) return sessionIdRef.current;
    const stored = localStorage.getItem(SESSION_KEY);
    if (stored) {
      try {
        const s = await getAgentSession(stored);
        setSessionId(s.session_id);
        sessionIdRef.current = s.session_id;
        if (s.messages?.length) {
          setMessages(s.messages as AgentMessage[]);
        }
        if (s.chips?.length) setChips(s.chips);
        if (s.ui_blocks?.length) {
          setUiBlocks(
            filterBlocksByOperator(
              mergeUiBlocks(s.ui_blocks as UIBlock[], [], pendingBlock, workflowBlock),
              operator
            )
          );
        }
        return s.session_id;
      } catch {
        localStorage.removeItem(SESSION_KEY);
      }
    }
    const created = await createAgentSession({
      sector_id: ctx.sectorId,
      focus: ctx.focus,
      workflow_step: ctx.workflowStep,
    });
    localStorage.setItem(SESSION_KEY, created.session_id);
    setSessionId(created.session_id);
    sessionIdRef.current = created.session_id;
    return created.session_id;
  }, [ctx.sectorId, ctx.focus, ctx.workflowStep, pendingBlock, workflowBlock, operator]);

  useEffect(() => {
    ensureSession().then(() => reloadProposals());
  }, [ensureSession, reloadProposals]);

  useEffect(() => {
    setUiBlocks((prev) =>
      filterBlocksByOperator(mergeUiBlocks(prev, proposalRef.current, pendingBlock, workflowBlock), operator)
    );
  }, [pendingBlock, workflowBlock, operator]);

  useEffect(() => {
    setUiBlocks((prev) => filterBlocksByOperator(prev, operator));
  }, [operator]);

  const recentUserTexts = () =>
    messagesRef.current
      .filter((m) => m.role === "user")
      .slice(-4)
      .map((m) => m.content);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || running) return;
      appendMessage("user", trimmed);
      setRunning(true);

      const sid = await ensureSession();
      const streamBlocks: UIBlock[] = [];
      let assistantMsgId: string | null = null;

      let summaryMsgId: string | null = null;

      try {
        await consumeAgentSessionStream(
          {
            session_id: sid,
            message: trimmed,
            sector_id: ctx.sectorId,
            focus: ctx.focus,
            workflow_step: ctx.workflowStep,
            recent_messages: recentUserTexts(),
            use_llm: true,
            stream_assistant: true,
            operator,
          },
          {
            onIntent: (intent) => {
              setChips(intent.suggested_chips?.length ? intent.suggested_chips : chipsRef.current);
              assistantMsgId = appendMessage("assistant", "", true);
            },
            onMessageDelta: (chunk) => {
              if (!assistantMsgId) return;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId ? { ...m, content: m.content + chunk, streaming: true } : m
                )
              );
            },
            onMessageDone: () => {
              if (assistantMsgId) patchMessage(assistantMsgId, { streaming: false });
            },
            onBlock: (block) => {
              streamBlocks.push(block);
              applyMergedBlocks(streamBlocks);
            },
            onSummaryDelta: (chunk) => {
              if (!summaryMsgId) {
                summaryMsgId = appendMessage("assistant", chunk, true);
                return;
              }
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === summaryMsgId ? { ...m, content: m.content + chunk, streaming: true } : m
                )
              );
            },
            onSummaryDone: () => {
              if (summaryMsgId) patchMessage(summaryMsgId, { streaming: false });
            },
            onRunComplete: (result) => {
              if (result.disclaimer) {
                appendMessage("system", result.disclaimer);
              }
              const blocks = (result.ui_blocks as UIBlock[]) || streamBlocks;
              if (blocks.length) applyMergedBlocks(blocks);
            },
            onSession: (id) => {
              localStorage.setItem(SESSION_KEY, id);
              setSessionId(id);
              sessionIdRef.current = id;
            },
            onNavigate: (route) => {
              if (ctx.onNavigate) ctx.onNavigate(route);
              else window.location.href = route;
            },
            onError: (detail) => {
              appendMessage("assistant", detail || "Agent 运行失败");
            },
          }
        );
        await reloadProposals();
        onReload?.();
        await persistSession();
      } catch (e: unknown) {
        const err = e as { message?: string };
        appendMessage("assistant", err.message || "Agent 运行失败");
      } finally {
        setRunning(false);
      }
    },
    [
      running,
      ctx.sectorId,
      ctx.focus,
      ctx.workflowStep,
      ctx.onNavigate,
      onReload,
      ensureSession,
      applyMergedBlocks,
      reloadProposals,
      persistSession,
    ]
  );

  const sendChip = (chip: string) => sendMessage(chip);

  const refreshAfterAction = async () => {
    await reloadProposals();
    onReload?.();
    await persistSession();
  };

  const adoptSector = async (recId: string, sectorName?: string) => {
    try {
      const r = await adoptSectorRecommendation(recId);
      const boot = r.bootstrap as {
        constituents?: { status?: string; reason?: string };
        report_draft?: { status?: string; draft_id?: string };
      } | null;
      const name = sectorName || "赛道";
      if (!boot) message.success(`已采纳赛道「${name}」`);
      else if (boot.constituents?.status === "skipped") {
        message.warning(`已采纳「${name}」；成分股同步跳过：${boot.constituents.reason ?? "未配置"}`);
      } else message.success(`已采纳「${name}」并触发赛道冷启动`);
      if (boot?.report_draft?.draft_id) message.info(`已生成知识草案 ${boot.report_draft.draft_id}`);
      await refreshAfterAction();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || "采纳失败");
    }
  };

  const runBlockAction = async (actionId: string) => {
    if (actionId === "resume_orchestrator" && ctx.sectorId) {
      setRunning(true);
      try {
        await sendMessage("从断点继续");
      } finally {
        setRunning(false);
      }
    }
  };

  const handleTodoAction = async (todo: WorkflowTodo) => {
    if (todo.action === "SyncConstituents" && ctx.sectorId) {
      try {
        const r = await syncSectorConstituents(ctx.sectorId);
        message.success(r.message ?? "成分股同步已触发");
        await refreshAfterAction();
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } } };
        message.error(err.response?.data?.detail ?? "同步失败");
      }
      return;
    }
    ctx.onNavigate?.(todo.route);
  };

  const resetSession = async () => {
    localStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    sessionIdRef.current = null;
    setMessages([{ id: nextId(), role: "assistant", content: DEFAULT_WELCOME, timestamp: Date.now() }]);
    setUiBlocks([]);
    await ensureSession();
    await reloadProposals();
  };

  return {
    messages,
    uiBlocks,
    chips,
    running,
    sessionId,
    sendMessage,
    sendChip,
    resetSession,
    runBlockAction,
    handleTodoAction,
    adoptSector,
    dismissSector: async (recId: string) => {
      await dismissSectorRecommendation(recId);
      await refreshAfterAction();
    },
    dismissBottleneck: async (recId: string) => {
      await dismissBottleneckRecommendation(recId);
      await refreshAfterAction();
    },
    confirmSerenity: async (recId: string, reason: string) => {
      await confirmSerenityRecommendation(recId, reason);
      message.success("已确认 Serenity 路径");
      await refreshAfterAction();
    },
    dismissSerenity: async (recId: string) => {
      await dismissSerenityRecommendation(recId);
      await refreshAfterAction();
    },
    rebutBear: async (bearId: string, rebuttal: string) => {
      await rebutBearCase(bearId, rebuttal);
      message.success("已回应看空论点");
      await refreshAfterAction();
    },
    confirmSectorBeta: async (sectorId: string, reason: string) => {
      try {
        await confirmSector(sectorId, true, reason, operator);
        message.success("已确认赛道景气，Agent 将自动推进后续阶段，到人工门控点暂停");
        await refreshAfterAction();
        // 一键投研主路径：确认景气后自动续跑编排器（stop_on_gate），人只在门控点裁决
        await sendMessage("从断点继续");
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } } };
        message.error(err.response?.data?.detail || "确认失败");
      }
    },
    navigate: (path: string) => ctx.onNavigate?.(path),
  };
}
