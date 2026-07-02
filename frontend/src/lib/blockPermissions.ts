/** 前端 Block / 交互权限 — 与 backend agent_block_permissions 对齐 */

export type UserOperator = "analyst" | "fund_manager" | "risk" | "admin" | "data_admin";

export const OPERATOR_ROLES: Record<UserOperator, string[]> = {
  analyst: ["researcher"],
  fund_manager: ["fund_manager", "researcher"],
  risk: ["risk", "researcher"],
  admin: ["researcher", "fund_manager", "risk", "knowledge_admin", "data_admin", "admin"],
  data_admin: ["data_admin", "knowledge_admin", "researcher"],
};

export const BLOCK_REQUIRED_ROLES: Record<string, string[]> = {
  metric_cards: [],
  pipeline_steps: [],
  workflow_progress: [],
  alert_feed: [],
  sector_recommendation_list: ["researcher", "fund_manager", "admin"],
  sector_pending_confirm_list: ["researcher", "fund_manager", "admin"],
  sector_settled_list: ["researcher", "fund_manager", "admin"],
  bottleneck_rec_list: ["researcher", "fund_manager", "admin"],
  serenity_rec_list: ["researcher", "fund_manager", "admin"],
  knowledge_draft_preview: ["researcher", "knowledge_admin", "data_admin", "admin"],
  report_draft_summary: ["researcher", "fund_manager", "admin"],
  candidate_fusion_table: ["fund_manager", "admin"],
  bear_case_list: ["researcher", "risk", "fund_manager", "admin"],
};

export const INTERACTION_REQUIRED_ROLES: Record<string, string[]> = {
  adopt_sector: ["fund_manager", "admin"],
  dismiss_proposal: ["researcher", "fund_manager", "risk", "admin", "data_admin"],
  confirm_serenity: ["researcher", "fund_manager", "admin"],
  confirm_sector_beta: ["researcher", "fund_manager", "admin"],
  rebut_bear: ["fund_manager", "risk", "admin"],
};

export function operatorNavRole(operator: UserOperator): string {
  const map: Record<UserOperator, string> = {
    analyst: "researcher",
    fund_manager: "fund_manager",
    risk: "risk",
    admin: "admin",
    data_admin: "data_admin",
  };
  return map[operator] ?? "researcher";
}

function rolesAllowed(operator: UserOperator, required: string[]): boolean {
  if (!required.length) return true;
  const roles = new Set(OPERATOR_ROLES[operator] ?? ["researcher"]);
  return required.some((r) => roles.has(r));
}

export function canViewBlock(operator: UserOperator, blockType: string, requiredRoles?: string[]): boolean {
  const req = requiredRoles?.length ? requiredRoles : BLOCK_REQUIRED_ROLES[blockType] ?? [];
  return rolesAllowed(operator, req);
}

export function canInteract(operator: UserOperator, action: keyof typeof INTERACTION_REQUIRED_ROLES): boolean {
  return rolesAllowed(operator, INTERACTION_REQUIRED_ROLES[action] ?? []);
}

export function filterBlocksByOperator<T extends { type: string; required_roles?: string[]; actions?: { action_id: string; required_roles?: string[] }[] }>(
  blocks: T[],
  operator: UserOperator
): T[] {
  return blocks
    .filter((b) => canViewBlock(operator, b.type, b.required_roles))
    .map((b) => ({
      ...b,
      actions: (b.actions || []).filter((a) =>
        rolesAllowed(operator, a.required_roles?.length ? a.required_roles : [])
      ),
    }));
}

export interface UiPermissions {
  operator: string;
  roles: string[];
  blocks: Record<string, boolean>;
  interactions: Record<string, boolean>;
}
