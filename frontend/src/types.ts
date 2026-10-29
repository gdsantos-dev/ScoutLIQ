import { tr } from "./i18n";
export type Currency = "BRL" | "USD";
export type Locale = "pt-BR" | "en-US" | "es";
export type Stage =
  "discovered" | "contacted" | "replied" | "negotiating" | "won" | "lost";
export type Page =
  | "radar"
  | "opportunities"
  | "monitors"
  | "actions"
  | "pipeline"
  | "intelligence"
  | "campaigns"
  | "clients"
  | "sites"
  | "finance"
  | "automations"
  | "integrations"
  | "settings"
  | "about";
export type User = {
  id: string;
  email: string;
  name: string;
  accent: string;
  motion: "full" | "reduced";
  timezone: string;
  locale: Locale;
  default_currency: Currency;
};
export type ScoreDimension = { value: number; max: number };
export type ScoreNicheExpectation = {
  key: string;
  label: string;
  importance: "high" | "medium" | "low";
  state: "present" | "missing" | "unknown";
};
export type ScoreNiche = {
  key: string;
  label: string;
  confidence: number;
  matched_term: string;
  matched_by: "category" | "name" | "fallback";
  expectations: ScoreNicheExpectation[];
};
export type ScoreConfidence = {
  value: number;
  level: "high" | "medium" | "low";
  components: Record<string, ScoreDimension>;
  missing: string[];
};
export type ServiceScore = {
  key: string;
  label: string;
  value: number;
  need: number;
  commercial_context: number;
  signals: string[];
};
export type ScoreDiagnosis = {
  key: string;
  area: string;
  severity: "high" | "medium" | "low";
  title: string;
  detail: string;
  evidence: string[];
  service_hints: string[];
};
export type CompetitiveContext = {
  status: "ready" | "insufficient";
  radius_km: number;
  peers_count: number;
  known_site_peers: number;
  peer_site_rate: number;
  strong_site_rate: number;
  median_reviews: number | null;
  median_rating: number | null;
  review_percentile: number | null;
  target_site_state: "strong" | "weak" | "missing" | "unknown";
  site_gap: "missing" | "weak" | "";
  demand_above_median: boolean;
  sample_quality: "high" | "medium" | "low";
  niche_key: string;
};
export type CommercialStructureSignal = {
  key: string;
  label: string;
  points: number;
  component: string;
};
export type CommercialStructure = {
  value: number;
  level: "high" | "medium" | "low";
  confidence: number;
  components: Record<string, ScoreDimension>;
  signals: CommercialStructureSignal[];
};
export type TimingSignal = {
  key: string;
  label: string;
  detail: string;
  points: number;
  effect: "positive" | "negative";
  at: number;
};
export type CommercialTiming = {
  value: number;
  level: "high" | "medium" | "low";
  signals: TimingSignal[];
  latest_event_at: number | null;
};
export type CombinedSignal = {
  key: string;
  label: string;
  strength: "high" | "medium" | "low";
  evidence: string[];
  recommended_action: string;
};
export type Score = {
  status?: string;
  coverage?: number;
  commercial_dimensions?: Record<
    string,
    { value: number | null; weight: number; state: string; reason: string }
  >;
  previous?: { version?: string; value?: number };
  value: number;
  version: string;
  reasons: { dimension: string; key: string; label: string; points: number }[];
  dimensions: Record<string, ScoreDimension>;
  niche: ScoreNiche;
  diagnosis: ScoreDiagnosis[];
  confidence: ScoreConfidence;
  service_scores: ServiceScore[];
  competitive: CompetitiveContext | null;
  commercial_structure: CommercialStructure;
  timing: CommercialTiming;
  combined_signals?: CombinedSignal[];
};
export type WebsiteIntelligenceFinding = {
  key: string;
  severity: string;
  detail: string;
};
export type WebsiteIntelligence = {
  quality_score?: number | null;
  high_findings?: number;
  medium_findings?: number;
  own_domain?: boolean;
  free_host_domain?: boolean;
  email?: boolean;
  forms?: number;
  social?: boolean;
  whatsapp_site?: boolean;
  analytics?: string[];
  technologies?: string[];
  booking?: boolean;
  ecommerce?: boolean;
  catalog_or_menu?: boolean;
  live_chat?: boolean;
  mixed_content?: number;
  pages_checked?: number;
  findings?: WebsiteIntelligenceFinding[];
};
export type LeadInput = {
  name: string;
  category: string;
  city: string;
  country: string;
  address: string;
  latitude: number;
  longitude: number;
  rating: number | null;
  reviews: number | null;
  website: string;
  website_status: "unknown" | "none" | "good" | "poor";
  instagram: string;
  instagram_active: boolean;
  phone: string;
  whatsapp: string;
  contact: string;
  potential_cents: number;
  potential_currency: Currency;
  notes: string;
};
export type Lead = LeadInput & {
  qualification?: Record<string, string>;
  contact_blocked?: boolean;
  id: string;
  stage: Stage;
  in_pipeline: boolean;
  demo: boolean;
  version: number;
  score: Score;
  source: string;
  next_action: string;
  next_action_on: string | null;
  pipeline_added_at: number | null;
  last_contact_at: number | null;
  website_intelligence: WebsiteIntelligence;
  website_analyzed_at: number | null;
  competitive_context: CompetitiveContext | null;
  competitive_analyzed_at: number | null;
  commercial_signal_analyzed_at: number | null;
  watchlisted: boolean;
  watch_started_at: number | null;
  watch_last_checked_at: number | null;
  watch_last_event_at: number | null;
  enrichment: LeadEnrichment;
  enrichment_analyzed_at: number | null;
  created_at: number;
};

export type RadarLocation = {
  id: string;
  name: string;
  uf: string;
  state: string;
  state_code?: string;
  country: string;
  country_code: string;
  formatted: string;
};

export type RadarSearchInput = {
  location: string;
  category: string;
  radius_km: number;
  scope: "region" | "radius" | "bounds" | "polygon";
  country: string;
  municipality_id?: string;
  city_name?: string;
  state?: string;
  state_code?: string;
  center_lat?: number | null;
  center_lng?: number | null;
  bounds?: [number, number, number, number] | [];
  polygon?: [number, number][];
};
export type RadarViewport = {
  west: number;
  south: number;
  east: number;
  north: number;
  center_lat: number;
  center_lng: number;
  radius_km: number;
};
export type RadarTerritory = { points: [number, number][] };
export type RadarOpportunityKey =
  | "no_site"
  | "website_issues"
  | "booking_gap"
  | "menu_gap"
  | "catalog_gap"
  | "ecommerce_gap"
  | "weak_digital"
  | "competitive_gap";
export type RadarSavedQuery = RadarSearchInput & {
  commercial_intent?: import("./searchTypes").CommercialIntent | null;
  problem_keys: RadarOpportunityKey[];
  min_score: number;
  min_rating: number;
  min_reviews: number;
  contact_filter: "" | "any" | "phone" | "whatsapp" | "instagram";
  min_confidence: number;
  min_timing: number;
  service_key: string;
  min_service_score: number;
};
export type RadarNaturalPlan = {
  query: RadarSavedQuery;
  detected: string[];
  unresolved: string[];
};
export type RadarSearchResponse = {
  provider: string;
  location: string;
  count: number;
  created: number;
  results: Lead[];
  complete?: boolean;
  scanned?: number;
  result_limit?: number | null;
  scope?: "region" | "radius" | "bounds" | "polygon";
  workspace_limit_reached?: boolean;
};

export type LeadActivityKind =
  | "whatsapp"
  | "call"
  | "email"
  | "meeting"
  | "proposal"
  | "reply"
  | "note"
  | "pipeline_added"
  | "stage_changed"
  | "next_action"
  | "next_action_cleared"
  | "sale_won"
  | "sale_reopened"
  | "watch_change";
export type LeadActivity = {
  id: string;
  lead_id: string;
  kind: LeadActivityKind;
  body: string;
  metadata: Record<string, unknown>;
  created_at: number;
};
export type LeadActivityCreateResponse = {
  activity: LeadActivity;
  lead: Lead;
};

export type RadarSavedSearch = {
  execution_mode?: "worker" | "legacy";
  worker_error?: string;
  id: string;
  name: string;
  query: RadarSavedQuery;
  last_result_ids: string[];
  last_new_count: number;
  last_run_at: number | null;
  monitor_enabled: boolean;
  monitor_interval: "daily" | "weekly";
  next_monitor_at: number | null;
  last_monitor_at: number | null;
  created_at: number;
  updated_at: number;
  version: number;
};

export type SimilarLead = Lead & { similarity: number };
export type SimilarLeadsResponse = {
  source_lead_id: string;
  discovered: number;
  count: number;
  results: SimilarLead[];
  basis: { category: string; city: string; niche: string };
};

export type GoogleMapsImportResponse = {
  source: "google_maps";
  source_id: string;
  resolved_url: string;
  warnings: string[];
  lead: Partial<LeadInput> & {
    latitude: number | null;
    longitude: number | null;
  };
};

export type LeadResearchEvidence = {
  key: string;
  value?: string;
};
export type LeadResearchCheck = {
  source_url?: string;
  key: string;
  state: "pass" | "warn" | "fail";
};
export type LeadResearchSource = {
  url: string;
  title: string;
  kind: string;
};
export type LeadAuditFinding = {
  key: string;
  severity: "high" | "medium" | "low";
  label: string;
  detail?: string;
};
export type LeadAuditCategory = { score: number; max: number };
export type LeadAudit = {
  level: "deep";
  quality_score: number;
  website_status: "unknown" | "good" | "poor";
  pages_checked: number;
  categories: Record<string, LeadAuditCategory>;
  findings: LeadAuditFinding[];
  angles: { key: string; label: string; evidence: string[] }[];
  pages: {
    url: string;
    title?: string;
    elapsed_ms?: number;
    body_bytes?: number;
  }[];
  signals: Record<string, string | number | boolean | string[]>;
  audited_at?: number;
  fetch_errors?: number;
};
export type LeadResearch = {
  id: string;
  lead_id: string;
  status: "confirmed" | "unverified" | "not_found";
  provider: string;
  website_url: string;
  website_status: "unknown" | "none" | "good" | "poor";
  confidence: number;
  evidence: LeadResearchEvidence[];
  checks: LeadResearchCheck[];
  sources: LeadResearchSource[];
  page: {
    title?: string;
    description?: string;
    lang?: string;
    elapsed_ms?: number;
    body_bytes?: number;
    domain?: string;
  };
  audit_level: "none" | "deep";
  audit: LeadAudit | Record<string, never>;
  audited_at: number | null;
  search_configured: boolean;
  candidates_checked: number;
  fetch_errors: number;
  checked_at: number;
};
export type LeadResearchResponse = {
  lead: Lead;
  research: LeadResearch;
};
export type LeadReanalysisResponse = {
  lead: Lead;
  research: LeadResearch | null;
  actions: ("web_research" | "deep_audit" | "competitive_refresh")[];
  status: "improved" | "checked" | "up_to_date";
  before_confidence: number;
  after_confidence: number;
};

export type LeadEnrichmentField = {
  value: string;
  source: string;
  confidence: number;
  checked_at: number;
};
export type LeadEnrichmentAttempt = {
  source: string;
  status: string;
  fields: string[];
  detail: string;
};
export type LeadEnrichment = {
  observed_contacts?: {
    field: string;
    value: string;
    source_url: string;
    observed_at: number;
    contact_authorized: false;
  }[];
  fields?: Record<string, LeadEnrichmentField>;
  attempts?: LeadEnrichmentAttempt[];
  coverage?: number;
  completed_at?: number;
  missing?: string[];
};
export type LeadEnrichmentResponse = {
  lead: Lead;
  enrichment: LeadEnrichment;
  research: LeadResearch | null;
};

export type AutomationTrigger =
  | "pipeline_added"
  | "stage_changed"
  | "watch_change"
  | "enriched"
  | "score_changed"
  | "manual";
export type AutomationConditionField =
  | "score"
  | "confidence"
  | "timing"
  | "stage"
  | "in_pipeline"
  | "watchlisted"
  | "has_phone"
  | "has_whatsapp"
  | "has_instagram"
  | "website_status"
  | "service_score"
  | "combined_signal";
export type AutomationOperator =
  "eq" | "neq" | "gte" | "lte" | "gt" | "lt" | "truthy" | "falsy" | "contains";
export type AutomationCondition = {
  field: AutomationConditionField;
  operator: AutomationOperator;
  value: string | number | boolean | null;
  service_key: string;
};
export type AutomationActionType =
  "add_pipeline" | "set_next_action" | "add_watchlist" | "add_note";
export type AutomationAction = {
  type: AutomationActionType;
  text: string;
  due_days: number;
};
export type AutomationStop = {
  stages: Stage[];
  max_runs_per_lead: number;
  stop_if_next_action_exists: boolean;
};
export type AutomationRule = {
  id: string;
  name: string;
  enabled: boolean;
  trigger: AutomationTrigger;
  conditions: AutomationCondition[];
  actions: AutomationAction[];
  stop: AutomationStop;
  last_run_at: number | null;
  created_at: number;
  updated_at: number;
  version: number;
};
export type AutomationRun = {
  id: string;
  rule_id: string;
  lead_id: string;
  trigger: string;
  status: "executed" | "stopped";
  reason: string;
  actions: { type: string; status: string; reason?: string; due_on?: string }[];
  created_at: number;
};

export type Payment = {
  id: string;
  amount_cents: number;
  paid_on: string;
  export_id: string;
  currency: Currency;
};
export type Sale = {
  id: string;
  lead_id: string;
  campaign_id: string | null;
  campaign_name: string;
  company: string;
  contact: string;
  phone: string;
  service: string;
  amount_cents: number;
  currency: Currency;
  received_cents: number;
  recurring_cents: number;
  project_status: "progress" | "active" | "finished";
  sold_on: string;
  due_on: string;
  demo: boolean;
  payments: Payment[];
};
export type CampaignMetrics = {
  members: number;
  in_pipeline: number;
  contacted: number;
  responded: number;
  negotiating: number;
  won: number;
  lost: number;
  attributed_sales: number;
  revenue_by_currency: Record<string, number>;
  recurring_by_currency: Record<string, number>;
};
export type Campaign = {
  id: string;
  name: string;
  description: string;
  status: "active" | "paused" | "finished";
  source_saved_search_id: string | null;
  created_at: number;
  updated_at: number;
  version: number;
  metrics: CampaignMetrics;
};
export type OutcomeInsight = {
  key: string;
  dimension: string;
  value: string;
  sample: number;
  won: number;
  lost: number;
  win_rate: number;
  delta_pp: number;
  direction: "higher" | "lower";
  explanation: string;
};
export type OutcomeInsights = {
  status: "ready" | "insufficient";
  closed_count: number;
  won_count: number;
  lost_count: number;
  overall_win_rate?: number;
  snapshot_coverage: number;
  minimum_required: number;
  note?: string;
  insights: OutcomeInsight[];
};
export type Expense = {
  id: string;
  description: string;
  amount_cents: number;
  currency: Currency;
  incurred_on: string;
  demo: boolean;
};
export type CurrencySummary = {
  today_cents: number;
  today_count: number;
  previous_cents: number;
  trend: { date: string; amount_cents: number }[];
  revenue_cents: number;
  received_cents: number;
  cost_cents: number;
  profit_cents: number;
  receivable_cents: number;
  recurring_cents: number;
};
export type Dashboard = CurrencySummary & {
  today: string;
  currency: Currency;
  by_currency: Partial<Record<Currency, CurrencySummary>>;
  has_demo: boolean;
};
export const stages: { id: Stage; label: string; symbol: string }[] = [
  { id: "discovered", label: "Encontrado", symbol: "○" },
  { id: "contacted", label: "Contatado", symbol: "↗" },
  { id: "replied", label: "Respondeu", symbol: "↔" },
  { id: "negotiating", label: "Negociando", symbol: "◐" },
  { id: "won", label: "Fechado", symbol: "✓" },
  { id: "lost", label: "Perdido", symbol: "−" },
];
export const stageLabel = (value: Stage) =>
  tr(stages.find((s) => s.id === value)?.label ?? value);
export const activeLocale = () =>
  ((typeof document !== "undefined" && document.documentElement.lang) ||
    "pt-BR") as Locale;
export const activeCurrency = () =>
  ((typeof document !== "undefined" &&
    document.documentElement.dataset.currency) ||
    "BRL") as Currency;
export const money = (
  cents: number,
  currency: Currency = activeCurrency(),
  locale: Locale = activeLocale(),
) =>
  new Intl.NumberFormat(locale, { style: "currency", currency }).format(
    cents / 100,
  );
export const dateLabel = (date: string, locale: Locale = activeLocale()) =>
  new Date(date + "T12:00:00").toLocaleDateString(locale, {
    day: "2-digit",
    month: "short",
  });
export const inputDate = (timezone = "America/Sao_Paulo") =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
export function cents(value: FormDataEntryValue | null): number {
  return Math.round(Number(value ?? 0) * 100);
}

export type InvestigationQualification = {
  class: "priority" | "promising" | "pending" | "low" | "unavailable";
  score: number;
  coverage: number;
  confidence?: { value: number; label: string };
  reasons: string[];
  pending: string[];
  decision: string;
  phase: string;
  state: string;
};
export type ResearchBatchItem = {
  qualification?: InvestigationQualification;
  lead_id: string;
  name: string;
  status: "pending" | "running" | "done" | "error" | "skipped" | "cancelled";
  outcome: string;
  error: string;
};
export type ResearchBatch = {
  ordinal?: number;
  execution_mode?: "worker" | "legacy";
  worker_error?: string;
  id: string;
  mode: "web" | "deep" | "progressive";
  status: "pending" | "running" | "paused" | "completed" | "cancelled";
  requested_count: number;
  skipped_recent: number;
  total: number;
  processed: number;
  pending: number;
  running: number;
  done: number;
  errors: number;
  created_at: number;
  updated_at: number;
  completed_at: number | null;
  items: ResearchBatchItem[];
};
export type ResearchBatchResponse = {
  batch: ResearchBatch | null;
  leads?: Lead[];
  lead?: Lead | null;
  existing?: boolean;
};

export type RadarViewState = {
  query: string;
  mode: string;
  sortBy: string;
  category: string;
  city: string;
  country: string;
  site: string;
  minScore: string;
  minRating: string;
  minReviews: string;
  contactFilter: string;
  pipelineFilter: string;
  minConfidence: string;
  minTiming: string;
  serviceFilter: string;
  opportunityFilter: RadarOpportunityKey | "";
  extraProblemKeys: RadarOpportunityKey[];
  smartList: string;
  visibleLimit: number;
  scrollY: number;
};
