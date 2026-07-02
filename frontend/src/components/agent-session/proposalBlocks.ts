import {
  getBearCases,
  getBottleneckRecommendations,
  getSectorRecommendations,
  getSerenityRecommendations,
  getSectors,
  type AlertItem,
  type Sector,
  type SectorRecommendation,
  type SectorWorkflowStatus,
  type UIBlock,
  type WorkflowTodo,
} from "../../lib/api";

const isConfirmed = (s: Sector) => s.status === "beta_confirmed" && s.human_confirmed;

function stableBlock(type: string, title: string, data: Record<string, unknown>, agentKey?: string): UIBlock {
  return {
    block_id: `proposal_${type}`,
    type,
    title,
    agent_key: agentKey,
    risk_level:
      type === "candidate_fusion_table" ||
      type === "bear_case_list" ||
      type === "sector_pending_confirm_list"
        ? "high"
        : "medium",
    data,
    actions: [],
  };
}

export function buildWorkflowProgressBlock(ws?: SectorWorkflowStatus | null): UIBlock | null {
  if (!ws?.steps?.length) return null;
  const actions =
    ws.resume_steps?.length
      ? [
          {
            action_id: "resume_orchestrator",
            label: `从断点继续（${ws.resume_steps.length} 步）`,
            kind: "primary" as const,
            ontology_action: "ResumeOrchestrator",
          },
        ]
      : [];
  return {
    block_id: "context_workflow_progress",
    type: "workflow_progress",
    title: `七步进度 · Step ${ws.current_step}${ws.sector_name ? ` · ${ws.sector_name}` : ""}`,
    agent_key: "orchestrator",
    risk_level: "low",
    data: { ...ws } as Record<string, unknown>,
    actions,
  };
}

/** 从 DB 加载待确认提案 → GUI Block */
export async function fetchProposalBlocks(sectorId?: string): Promise<UIBlock[]> {
  const [proposedRecs, allRecs, sectors, bottleneckRecs, serenityRecs, bearCases] = await Promise.all([
    getSectorRecommendations("proposed"),
    getSectorRecommendations(),
    getSectors(),
    sectorId ? getBottleneckRecommendations(sectorId, "proposed") : Promise.resolve([]),
    sectorId ? getSerenityRecommendations(sectorId, "proposed") : Promise.resolve([]),
    sectorId ? getBearCases(sectorId, undefined, "unrebutted") : Promise.resolve([]),
  ]);

  const recBySector = (id: string) => allRecs.find((r) => r.sector_id === id);

  const blocks: UIBlock[] = [];

  const pending = sectors.filter((s) => !isConfirmed(s) && s.status !== "rejected");
  if (pending.length) {
    blocks.push(
      stableBlock(
        "sector_pending_confirm_list",
        `待确认赛道景气（${pending.length} 项 · ConfirmSectorBeta）`,
        {
          items: pending.map((sector) => ({
            sector,
            recommendation: recBySector(sector.id) as SectorRecommendation | undefined,
          })),
        },
        "confirm_sector"
      )
    );
  }

  if (proposedRecs.length) {
    blocks.push(
      stableBlock(
        "sector_recommendation_list",
        `待采纳赛道（${proposedRecs.length} 条）`,
        { items: proposedRecs },
        "sector_recommend"
      )
    );
  }
  if (bottleneckRecs.length) {
    blocks.push(
      stableBlock(
        "bottleneck_rec_list",
        `待确认瓶颈（${bottleneckRecs.length} 条）`,
        { items: bottleneckRecs },
        "bottleneck_scout"
      )
    );
  }
  if (serenityRecs.length) {
    blocks.push(
      stableBlock(
        "serenity_rec_list",
        `待确认 Serenity 路径（${serenityRecs.length} 条）`,
        { items: serenityRecs },
        "serenity_path"
      )
    );
  }
  if (bearCases.length) {
    blocks.push(
      stableBlock(
        "bear_case_list",
        `待回应看空论点（${bearCases.length} 条）`,
        { items: bearCases, sector_id: sectorId },
        "bear_case"
      )
    );
  }

  const settled = sectors.filter((s) => isConfirmed(s) || s.status === "rejected");
  if (settled.length) {
    blocks.push(
      stableBlock(
        "sector_settled_list",
        `已处理赛道（${settled.length} 项）`,
        { items: settled },
        "confirm_sector"
      )
    );
  }

  return blocks;
}

export function buildPendingTodosBlock(
  todos: WorkflowTodo[],
  alerts: AlertItem[],
  resumeSteps?: string[]
): UIBlock | null {
  if (!todos.length && !alerts.length) return null;
  const items = [
    ...todos.map((t) => ({ ...t, kind: "todo" as const })),
    ...alerts.map((a) => ({ ...a, kind: "alert" as const })),
  ];
  const actions =
    resumeSteps && resumeSteps.length
      ? [
          {
            action_id: "resume_orchestrator",
            label: `从断点继续（${resumeSteps.length} 步）`,
            kind: "primary" as const,
            ontology_action: "ResumeOrchestrator",
          },
        ]
      : [];
  return {
    block_id: "pending_todos",
    type: "alert_feed",
    title: `待处理（${todos.length} 项待办${alerts.length ? `，${alerts.length} 条告警` : ""}）`,
    risk_level: "low",
    data: { items, resume_steps: resumeSteps },
    actions,
  };
}

/** 合并 Agent 运行 Block 与持久提案 Block */
export function mergeUiBlocks(
  agentBlocks: UIBlock[],
  proposalBlocks: UIBlock[],
  pendingBlock: UIBlock | null,
  workflowBlock: UIBlock | null = null
): UIBlock[] {
  const seen = new Set<string>();
  const out: UIBlock[] = [];

  const push = (b: UIBlock) => {
    const key =
      b.block_id.startsWith("proposal_") ||
      b.block_id === "pending_todos" ||
      b.block_id === "context_workflow_progress"
        ? b.block_id
        : b.type + b.block_id;
    if (seen.has(key)) return;
    seen.add(key);
    out.push(b);
  };

  if (pendingBlock) push(pendingBlock);
  if (workflowBlock) push(workflowBlock);

  const agentTypes = new Set(agentBlocks.map((b) => b.type));
  for (const b of proposalBlocks) {
    if (!agentTypes.has(b.type)) push(b);
  }
  for (const b of agentBlocks) push(b);

  return out;
}
