import axios from "axios";

export const api = axios.create({ baseURL: "/api/v1" });

export interface Sector {
  id: string;
  name: string;
  status: string;
  demand_growth_hint: number | null;
  human_confirmed: boolean;
}

export interface GraphNode {
  id: string;
  label: string;
  type: "product" | "company";
  layer?: string;
  bottleneck_status?: string;
  serenity_niche?: boolean;
  hint_score?: number;
  hint_level?: string;
  market_cap_billion?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface SectorGraph {
  sector_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  note: string;
}

export interface Candidate {
  stock_code: string;
  name: string;
  mode: string;
  role?: string;
  priority?: string;
  tag?: string;
  product_name: string;
  hint_score: number;
  hint_type?: string;
  status: string;
  in_buy_side?: boolean;
  in_serenity?: boolean;
  trace?: string;
  hop_count?: number;
  rationale: string;
  market_cap_billion?: number;
  analyst_coverage?: number;
}

export interface CandidateResponse {
  sector_id: string;
  mode: string;
  count: number;
  items: Candidate[];
  note: string;
}

export interface LogicStep {
  step: number;
  type: string;
  claim: string;
  citations: string[];
  confidence: string;
  human_confirmed: boolean;
}

export interface CounterArg {
  risk: string;
  severity: string;
  note: string;
}

export interface Citation {
  ref_id: string;
  source_type: string;
  source_ref: string;
  excerpt: string;
}

export interface Report {
  report_id: string;
  status: string;
  sector_id: string;
  mode: string;
  generated_by: string;
  logic_chain: LogicStep[];
  counter_arguments: CounterArg[];
  candidates: { stock_code: string; name: string; role?: string; priority?: string; thesis_summary: string }[];
  citations: Citation[];
  unverified_claims: string[];
  generated_at: string;
  disclaimer: string;
}

export const getSectors = () => api.get<{ items: Sector[] }>("/sectors").then((r) => r.data.items);

export const getSectorGraph = (sectorId: string) =>
  api.get<SectorGraph>(`/graph/sector/${sectorId}`).then((r) => r.data);

export const getCandidates = (sectorId: string, mode: string) =>
  api.get<CandidateResponse>("/candidates", { params: { sector_id: sectorId, mode } }).then((r) => r.data);

export const confirmCandidates = (body: {
  sector_id: string;
  mode: string;
  stock_codes: string[];
  action: "confirmed" | "rejected";
  reason: string;
  operator?: string;
}) => api.post("/candidates/confirm", body).then((r) => r.data);

/** Ontology Action API — 推荐新代码使用 */
export const executeOntologyAction = (
  actionType: string,
  target: { type: string; id: string },
  params: Record<string, unknown>,
  operator = "analyst"
) =>
  api
    .post(`/ontology/actions/${actionType}/execute`, { target, params, operator })
    .then((r) => r.data);

export const batchPoolAction = (body: {
  sector_id: string;
  mode: string;
  stock_codes: string[];
  reason: string;
  operator?: string;
  actionType: "ApprovePoolEntry" | "RejectPoolEntry";
}) =>
  api
    .post(`/ontology/actions/${body.actionType}/batch-pool`, {
      sector_id: body.sector_id,
      mode: body.mode,
      stock_codes: body.stock_codes,
      reason: body.reason,
      operator: body.operator ?? "analyst",
    })
    .then((r) => r.data);

export const getActionTypes = () =>
  api.get<{ items: { name: string; display_name: string; parameters: unknown[] }[] }>(
    "/ontology/registry/action-types"
  ).then((r) => r.data.items);

export const invokeOntologyFunction = (name: string, inputs: Record<string, unknown>) =>
  api.post(`/ontology/functions/${name}/invoke`, { inputs }).then((r) => r.data);

export const getObjectSet = (setName: string, sectorId: string, mode = "fusion") =>
  api
    .get(`/ontology/object-sets/${setName}`, { params: { sector_id: sectorId, mode } })
    .then((r) => r.data);

export const getProductHintScore = (productId: string) =>
  api.get(`/graph/product/${productId}/hint-score`).then((r) => r.data);

export const generateReport = (sectorId: string, mode: string) =>
  api.post<Report>("/reasoning/graphrag", { sector_id: sectorId, mode }).then((r) => r.data);

export const reviewReport = (reportId: string, action: string, comments: string) =>
  api.post(`/reasoning/reports/${reportId}/review`, { action, comments }).then((r) => r.data);
