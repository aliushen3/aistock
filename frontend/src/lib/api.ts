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
  freshness?: string;
}

export interface EdgeAssessment {
  priced_in: string;
  crowding_percentile?: number | null;
  pe_percentile?: number | null;
  degraded?: boolean;
  flag?: string | null;
}

export interface ValueCaptureCard {
  captures_economics: string;
  gross_margin?: number | null;
  pricing_mechanism?: string;
  degraded?: boolean;
  flag?: string | null;
}

export interface BearCase {
  bear_id: string;
  sector_id: string;
  candidate_id?: string | null;
  stock_code: string;
  risk: string;
  dimension: string;
  severity: string;
  probability: string;
  what_would_confirm: string;
  citations: string[];
  rebuttal?: string | null;
  rebuttal_status: string;
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
  close_price?: number;
  pe_percentile?: number;
  gross_margin?: number;
  roe?: number;
  market_data_date?: string;
  market_data_source?: string;
  financial_data_date?: string;
  financial_data_source?: string;
  data_origin?: "ods" | "seed";
  edge_assessment?: EdgeAssessment;
  value_capture?: ValueCaptureCard;
  bear_status?: string;
}

export interface CandidateResponse {
  sector_id: string;
  mode: string;
  count: number;
  items: Candidate[];
  gated?: boolean;
  gate_message?: string;
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
  rag_context?: { retrieval_count: number; retrieval_mode: string };
}

export const getSectors = () => api.get<{ items: Sector[] }>("/sectors").then((r) => r.data.items);

export interface SectorRecommendation {
  rec_id: string;
  run_id: string;
  sector_name: string;
  sector_id: string | null;
  is_new: boolean;
  beta_score: number;
  demand_growth_hint?: number | null;
  signals: {
    demand_growth_ok?: boolean;
    capex_positive?: boolean;
    research_support_count?: number;
  };
  rationale: string;
  terminal_products: string[];
  evidence_refs: { ref_id?: string; excerpt?: string }[];
  risks: string[];
  next_actions: string[];
  status: string;
  agent_mode: string;
  created_at?: string;
}

export interface SectorRecommendRunResult extends AgentRunSummary {
  run_id: string;
  agent: string;
  agent_mode: string;
  llm_enabled: boolean;
  agent_summary: string;
  context_stats: {
    existing_sectors: number;
    metrics_signals: number;
    evidence_hits: number;
    report_themes?: number;
    watchlist_count?: number;
    watchlist_sources?: Record<string, number>;
  };
  recommendations: SectorRecommendation[];
  disclaimer: string;
}

export interface WatchlistItem {
  sector_name: string;
  sector_id: string | null;
  keywords: string[];
  terminal_products: string[];
  source: string;
  confidence?: string;
  evidence_refs?: { ref_id?: string; excerpt?: string }[];
  human_confirmed?: boolean;
  status?: string;
}

export interface WatchlistResponse {
  dynamic: boolean;
  watchlist: WatchlistItem[];
  watchlist_count: number;
  source_counts: Record<string, number>;
  report_themes: {
    uploaded_doc_count: number;
    snippet_count: number;
    themes: WatchlistItem[];
    extraction_mode: string;
  };
}

export interface BottleneckRecommendation {
  rec_id: string;
  sector_id: string;
  product_id: string;
  product_name: string;
  hint_level: string;
  hint_score: number;
  rationale: string;
  status: string;
}

export interface SerenityRecommendation {
  rec_id: string;
  sector_id: string;
  path_id: string;
  niche_product_id: string;
  niche_product_name: string;
  hop_count: number;
  serenity_hint: number;
  rationale: string;
  status: string;
}

export interface DataAdapterInfo {
  kind?: string;
  name: string;
  mode: string;
  default?: boolean;
  live_configured?: boolean;
  tushare_configured?: boolean;
  gateway_url?: string | null;
}

export interface AgentRunSummary {
  run_id?: string;
  agent: string;
  agent_mode?: string;
  agent_summary?: string;
  disclaimer?: string;
  [key: string]: unknown;
}

export const getWatchlist = (focus?: string) =>
  api
    .get<WatchlistResponse>("/agents/watchlist", { params: focus ? { focus } : undefined })
    .then((r) => r.data);

export const getDataAdapters = () =>
  api.get<{ items: DataAdapterInfo[]; default: string }>("/data/adapters").then((r) => r.data);

export interface OdsStats {
  enabled: boolean;
  industry_metrics?: number;
  research_reports?: number;
  market_daily?: number;
  announcements?: number;
  financials?: number;
  external_reports?: number;
}

export const getOdsStats = () => api.get<OdsStats>("/data/ods/stats").then((r) => r.data);

export const syncSectorMetrics = (sectorId: string, adapter?: string) =>
  api.post(`/data/sync/metrics/${sectorId}`, null, { params: adapter ? { adapter } : undefined }).then((r) => r.data);

export const syncSectorMarket = (sectorId: string, adapter?: string) =>
  api.post(`/data/sync/market/${sectorId}`, null, { params: adapter ? { adapter } : undefined }).then((r) => r.data);

export const syncSectorAnnouncements = (sectorId: string, adapter?: string) =>
  api
    .post(`/data/sync/announcements/${sectorId}`, null, { params: adapter ? { adapter } : undefined })
    .then((r) => r.data);

export const syncSectorFinancials = (sectorId: string, adapter?: string) =>
  api
    .post(`/data/sync/financials/${sectorId}`, null, { params: adapter ? { adapter } : undefined })
    .then((r) => r.data);

export const syncSectorReports = (sectorId: string, adapter?: string) =>
  api.post(`/data/sync/reports/${sectorId}`, null, { params: adapter ? { adapter } : undefined }).then((r) => r.data);

export const ingestSectorReports = (sectorId: string) =>
  api.post(`/data/reports/${sectorId}/ingest`).then((r) => r.data);

export const runKnowledgeIngestAgent = (body: {
  sector_id: string;
  source_ref: string;
  content: string;
  source_type?: string;
}) => api.post<AgentRunSummary>("/agents/knowledge-ingest/run", body).then((r) => r.data);

export const runBottleneckScoutAgent = (body: { sector_id: string; min_hint_level?: string }) =>
  api.post<AgentRunSummary>("/agents/bottleneck-scout/run", body).then((r) => r.data);

export const runSerenityPathAgent = (body: { sector_id: string; min_serenity_hint?: number }) =>
  api.post<AgentRunSummary>("/agents/serenity-path/run", body).then((r) => r.data);

export const runReportGraphRAGAgent = (body: { sector_id: string; mode?: string }) =>
  api.post<AgentRunSummary>("/agents/report-graphrag/run", body).then((r) => r.data);

export const runCandidateFusionAgent = (body: { sector_id: string; mode?: string }) =>
  api.post<AgentRunSummary>("/agents/candidate-fusion/run", body).then((r) => r.data);

export const runMonitorWatchAgent = (body: { sector_id?: string; mode?: string }) =>
  api.post<AgentRunSummary>("/agents/monitor-watch/run", body).then((r) => r.data);

export const runOrchestrator = (body: {
  sector_id?: string;
  focus?: string;
  query?: string;
  content?: string;
  mode?: string;
  steps?: string[];
  stop_on_gate?: boolean;
}) => api.post<AgentRunSummary>("/agents/orchestrator/run", body).then((r) => r.data);

export const getBottleneckRecommendations = (sectorId?: string, status?: string) =>
  api
    .get<{ items: BottleneckRecommendation[] }>("/agents/bottleneck-recommendations", {
      params: { sector_id: sectorId, status },
    })
    .then((r) => r.data.items);

export const dismissBottleneckRecommendation = (recId: string) =>
  api.post(`/agents/bottleneck-recommendations/${recId}/dismiss`).then((r) => r.data);

export const getSerenityRecommendations = (sectorId?: string, status?: string) =>
  api
    .get<{ items: SerenityRecommendation[] }>("/agents/serenity-recommendations", {
      params: { sector_id: sectorId, status },
    })
    .then((r) => r.data.items);

export const confirmSerenityRecommendation = (recId: string, reason: string) =>
  api
    .post(`/agents/serenity-recommendations/${recId}/confirm`, null, {
      params: { reason, operator: "analyst" },
    })
    .then((r) => r.data);

export const dismissSerenityRecommendation = (recId: string) =>
  api.post(`/agents/serenity-recommendations/${recId}/dismiss`).then((r) => r.data);

export const runSectorRecommendAgent = (body: {
  focus?: string;
  query?: string;
  max_recommendations?: number;
}) => api.post<SectorRecommendRunResult>("/agents/sector-recommend/run", body).then((r) => r.data);

export const getSectorRecommendations = (status?: string) =>
  api
    .get<{ items: SectorRecommendation[] }>("/agents/sector-recommendations", { params: { status } })
    .then((r) => r.data.items);

export const adoptSectorRecommendation = (recId: string) =>
  api.post(`/agents/sector-recommendations/${recId}/adopt`).then((r) => r.data);

export const dismissSectorRecommendation = (recId: string) =>
  api.post(`/agents/sector-recommendations/${recId}/dismiss`).then((r) => r.data);

export const confirmSector = (sectorId: string, confirmed: boolean, reason: string, operator = "analyst") =>
  api
    .post(`/sectors/${sectorId}/confirm`, { confirmed, reason, operator })
    .then((r) => r.data);

export const getHealth = () => api.get("/health").then((r) => r.data);

export interface AlertItem {
  level: string;
  type: string;
  message: string;
  action?: string;
  count?: number;
}

export const getAlerts = (sectorId: string, mode = "fusion") =>
  api
    .get<{ items: AlertItem[]; count: number }>(`/alerts/sector/${sectorId}`, { params: { mode } })
    .then((r) => r.data);

export const getGlobalAlerts = () =>
  api.get<{ items: AlertItem[]; count: number }>("/alerts/global").then((r) => r.data);

export const ingestKnowledgeAsync = (body: {
  sector_id: string;
  source_type: string;
  source_ref: string;
  content: string;
}) => api.post("/knowledge/ingest/async", body).then((r) => r.data);

export interface SerenityPath {
  path_id: string;
  node_ids: string[];
  node_names: string[];
  niche_product_id: string;
  niche_product_name: string;
  hop_count: number;
  serenity_hint: number;
  status: string;
}

export const getSerenityTrace = (sectorId: string) =>
  api
    .get<{ paths: SerenityPath[]; count: number }>(`/reasoning/serenity/trace`, { params: { sector_id: sectorId } })
    .then((r) => r.data);

export interface MetricItem {
  sector_id: string;
  product_id: string | null;
  product_name: string | null;
  metric_key: string;
  metric_label: string;
  period: string;
  value: number;
  unit: string;
}

export interface DashboardData {
  sector_id: string;
  sector_name: string;
  sector_status?: string;
  sector_metrics: MetricItem[];
  product_cards: {
    product_id: string;
    product_name: string;
    bottleneck_status: string;
    capacity_utilization: number | null;
    price_or_shipment_yoy: number | null;
    metrics: MetricItem[];
  }[];
  material_metrics?: {
    material_key: string;
    price: number | null;
    unit: string;
    price_yoy: number | null;
    period: string;
    data_source: string;
  }[];
  note: string;
}

export const getDashboard = (sectorId: string) =>
  api
    .get<{ gated: boolean; message?: string; dashboard: DashboardData }>(
      `/metrics/sector/${sectorId}/dashboard`
    )
    .then((r) => r.data);

export interface AuditEntry {
  id: number;
  action: string;
  operator: string;
  target: string;
  detail?: Record<string, unknown>;
  created_at?: string;
}

export const getAuditLog = () => api.get<{ items: AuditEntry[] }>("/candidates/audit").then((r) => r.data);

export interface DiagnosisItem {
  stock_code: string;
  name: string;
  verdict: string;
  verdict_label: string;
  retail_score: number;
  professional_score: number;
  signals: { type: string; signal: string; detail: string }[];
  advice: string;
}

export const getDiagnosis = (sectorId: string) =>
  api.get<{ items: DiagnosisItem[]; count: number }>(`/diagnosis/sector/${sectorId}`).then((r) => r.data);

export interface KnowledgeDraft {
  draft_id: string;
  sector_id: string;
  source_type: string;
  source_ref: string;
  extracted: {
    relations?: { source_name: string; target_name: string }[];
    bottleneck_hints?: { product_name: string }[];
  };
  status: string;
}

export const ingestKnowledge = (body: {
  sector_id: string;
  source_type: string;
  source_ref: string;
  content: string;
}) => api.post("/knowledge/ingest", body).then((r) => r.data);

export interface UploadedDocument {
  doc_id: string;
  sector_id: string;
  source_ref: string;
  filename: string;
  char_count: number;
  chunk_count: number;
  storage_path?: string | null;
  status: string;
  created_at?: string;
}

export interface UploadReportResult {
  doc_id: string;
  source_ref: string;
  filename: string;
  char_count: number;
  chunk_count: number;
  storage_path?: string | null;
  vector_index: { status: string; count: number };
  draft_id?: string | null;
  message: string;
}

export const uploadResearchReport = (
  file: File,
  sectorId: string,
  sourceRef?: string,
  extractKnowledge = true
) => {
  const form = new FormData();
  form.append("file", file);
  form.append("sector_id", sectorId);
  if (sourceRef) form.append("source_ref", sourceRef);
  form.append("extract_knowledge", String(extractKnowledge));
  return api
    .post<UploadReportResult>("/knowledge/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    })
    .then((r) => r.data);
};

export const getUploadedDocuments = (sectorId: string) =>
  api
    .get<{ items: UploadedDocument[] }>("/knowledge/documents", { params: { sector_id: sectorId } })
    .then((r) => r.data.items);

export const getKnowledgeDrafts = (sectorId: string) =>
  api.get<{ items: KnowledgeDraft[] }>("/knowledge/drafts", { params: { sector_id: sectorId } }).then((r) => r.data);

export const confirmKnowledgeDraft = (draftId: string) =>
  api.post(`/knowledge/drafts/${draftId}/confirm`).then((r) => r.data);

export const getPendingReviews = () =>
  api.get<{ items: { pending_id: string; action_type: string; target_id: string; first_operator: string }[] }>(
    "/ontology/pending-reviews"
  ).then((r) => r.data);

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

/** v3.0 主线一：BearCase 看空对抗 */
export const runBearCaseAgent = (body: { sector_id: string; mode?: string }) =>
  api.post<AgentRunSummary & { bear_cases: BearCase[] }>("/agents/bear-case/run", body).then((r) => r.data);

export const getBearCases = (sectorId?: string, stockCode?: string, status?: string) =>
  api
    .get<{ items: BearCase[] }>("/agents/bear-cases", {
      params: { sector_id: sectorId, stock_code: stockCode, status },
    })
    .then((r) => r.data.items);

export const rebutBearCase = (bearId: string, rebuttal: string, operator = "analyst") =>
  executeOntologyAction("RebutBearCase", { type: "BearCase", id: bearId }, { rebuttal }, operator);

/** v3.0 主线二：保鲜过期知识 */
export interface StaleKnowledgeItem {
  product_id: string;
  product_name: string;
  freshness: string;
  valid_until?: string | null;
  age_days?: number | null;
}

export const getStaleKnowledge = (sectorId?: string) =>
  api
    .get<{ count: number; items: StaleKnowledgeItem[] }>("/knowledge/stale", {
      params: { sector_id: sectorId },
    })
    .then((r) => r.data);
