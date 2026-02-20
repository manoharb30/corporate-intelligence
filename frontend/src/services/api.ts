import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface Company {
  id: string
  name: string
  normalized_name?: string
  cik?: string
  lei?: string
  jurisdiction?: string
  incorporation_date?: string
  status?: string
}

export interface Person {
  id: string
  name: string
  normalized_name?: string
  is_pep: boolean
  is_sanctioned: boolean
}

export interface Filing {
  id: string
  accession_number: string
  form_type: string
  filing_date: string
  source_url?: string
}

export interface GraphNode {
  id: string
  label: string
  type: string
  properties: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  properties: Record<string, unknown>
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

// Company Search types
export interface CompanySearchResult {
  cik: string
  name: string
  ticker: string | null
  in_graph: boolean
  company_id: string | null
}

export interface CompanySearchResponse {
  query: string
  results: CompanySearchResult[]
  graph_count: number
  edgar_count: number
}

// Company Intelligence types
export interface PersonSummary {
  id: string
  name: string
  title: string | null
  is_officer: boolean
  is_director: boolean
  is_beneficial_owner: boolean
  ownership_percentage: number | null
  other_companies_count: number
  is_sanctioned: boolean
  is_pep: boolean
}

export interface SubsidiarySummary {
  id: string
  name: string
  jurisdiction: string | null
  ownership_percentage: number | null
}

export interface RedFlag {
  type: string
  severity: string
  description: string
  entity_id: string | null
  entity_name: string | null
}

export interface CompanyIntelligence {
  company_id: string
  company_name: string
  cik: string | null
  jurisdiction: string | null
  officers: PersonSummary[]
  directors: PersonSummary[]
  beneficial_owners: PersonSummary[]
  subsidiaries: SubsidiarySummary[]
  parent_company: SubsidiarySummary | null
  red_flags: RedFlag[]
  data_freshness: string | null
  filings_count: number
}

// Companies API
export const companiesApi = {
  list: (page = 1, pageSize = 20) =>
    api.get<PaginatedResponse<Company>>('/companies', { params: { page, page_size: pageSize } }),

  get: (id: string) => api.get<Company>(`/companies/${id}`),

  search: (query: string, limit = 20) =>
    api.get<CompanySearchResponse>('/companies/search', { params: { q: query, limit } }),

  getIntelligence: (id: string) =>
    api.get<CompanyIntelligence>(`/companies/${id}/intelligence`),

  getOwnershipChain: (id: string, maxDepth = 10) =>
    api.get(`/companies/${id}/ownership-chain`, { params: { max_depth: maxDepth } }),

  getSubsidiaries: (id: string, maxDepth = 5) =>
    api.get<Company[]>(`/companies/${id}/subsidiaries`, { params: { max_depth: maxDepth } }),
}

// Persons API
export const personsApi = {
  list: (page = 1, pageSize = 20) =>
    api.get<PaginatedResponse<Person>>('/persons', { params: { page, page_size: pageSize } }),

  get: (id: string) => api.get<Person>(`/persons/${id}`),

  search: (query: string, limit = 10) =>
    api.get<Person[]>('/persons/search', { params: { q: query, limit } }),

  listPeps: (limit = 50) => api.get<Person[]>('/persons/pep', { params: { limit } }),

  listSanctioned: (limit = 50) => api.get<Person[]>('/persons/sanctioned', { params: { limit } }),
}

// Filings API
export const filingsApi = {
  list: (page = 1, pageSize = 20, formType?: string) =>
    api.get<PaginatedResponse<Filing>>('/filings', {
      params: { page, page_size: pageSize, form_type: formType },
    }),

  get: (id: string) => api.get<Filing>(`/filings/${id}`),

  getFormTypes: () => api.get<Array<{ form_type: string; count: number }>>('/filings/form-types'),
}

// Graph API
export const graphApi = {
  getEntityGraph: (entityId: string, depth = 2, includeFilings = false) =>
    api.get<GraphData>(`/graph/entity/${entityId}`, {
      params: { depth, include_filings: includeFilings },
    }),

  getOwnershipGraph: (entityId: string, direction = 'both', maxDepth = 5) =>
    api.get<GraphData>(`/graph/ownership/${entityId}`, {
      params: { direction, max_depth: maxDepth },
    }),

  findPath: (sourceId: string, targetId: string, maxDepth = 6) =>
    api.get<GraphData>('/graph/path', {
      params: { source_id: sourceId, target_id: targetId, max_depth: maxDepth },
    }),

  getAddressClusters: (minEntities = 5, limit = 20) =>
    api.get('/graph/address-clusters', { params: { min_entities: minEntities, limit } }),

  getRiskIndicators: (entityId: string) =>
    api.get(`/graph/risk-indicators/${entityId}`),
}

// Health API
export const healthApi = {
  check: () => api.get('/health'),
  checkDb: () => api.get('/health/db'),
}

// Feed types
export interface InsiderContextData {
  net_direction: 'buying' | 'selling' | 'mixed' | 'none'
  total_buy_value: number
  total_sell_value: number
  notable_trades: string[]
  cluster_activity: boolean
  trade_count: number
  person_matches: string[]
  near_filing_count: number
  near_filing_direction: 'buying' | 'selling' | 'mixed' | 'none'
}

export interface ClusterBuyerDetail {
  name: string
  title: string
  total_value: number
  trade_count: number
}

export interface ClusterDetail {
  window_start: string
  window_end: string
  num_buyers: number
  buyers: ClusterBuyerDetail[]
}

export interface SignalItem {
  company_name: string
  cik: string
  ticker: string | null
  filing_date: string
  signal_level: 'high' | 'medium' | 'low'
  signal_summary: string
  items: string[]
  item_names: string[]
  persons_mentioned: string[]
  accession_number: string
  combined_signal_level: 'critical' | 'high_bearish' | 'high' | 'medium' | 'low'
  insider_context: InsiderContextData | null
  signal_type?: 'insider_cluster' | '8k'
  cluster_detail?: ClusterDetail
}

export interface CompanyFilter {
  cik: string
  name: string
  ticker: string | null
}

export interface FeedResponse {
  total: number
  by_level: {
    high: number
    medium: number
    low: number
  }
  by_combined: {
    critical: number
    high_bearish: number
    high: number
    medium: number
    low: number
  }
  signals: SignalItem[]
  company_filter?: CompanyFilter
}

export interface DbStats {
  companies: number
  events: number
  persons: number
  insider_transactions: number
  jurisdictions: number
  total_nodes: number
  total_relationships: number
}

export interface FeedSummary {
  daily_counts: Array<{ date: string; count: number }>
  item_counts: Record<string, number>
  total_events: number
}

// Insider Trade types
export interface InsiderTrade {
  insider_name: string
  insider_title: string
  transaction_date: string
  transaction_code: string
  transaction_type: string
  security_title: string
  shares: number
  price_per_share: number
  total_value: number
  shares_after_transaction: number
  ownership_type: string
  is_derivative: boolean
  filing_date: string
  accession_number: string
}

export interface InsiderTradeSummary {
  total_transactions: number
  unique_insiders: number
  purchases: number
  sales: number
  awards: number
  exercises_held: number
  other: number
  total_purchase_value: number
  total_sale_value: number
  net_value: number
  signal_level: string
  signal_summary: string
  buying_insiders: string[]
}

export interface InsiderTradesResponse {
  cik: string
  total: number
  trades: InsiderTrade[]
}

// Profile types
export interface CompanyProfile {
  basic_info: {
    cik: string
    name: string
    ticker: string | null
    sic: string | null
    sic_description: string | null
    state_of_incorporation: string | null
  }
  counts: {
    subsidiaries: number
    officers: number
    directors: number
    board_connections: number
    insider_trades: number
  }
  signals: Array<{
    filing_date: string
    item_number: string
    item_name: string
    signal_type: string
    persons_mentioned: string[]
    accession_number: string
  }>
  connections: Array<{
    company_name: string
    cik: string
    shared_directors: string[]
  }>
  officers: Array<{
    name: string
    title: string | null
  }>
  directors: Array<{
    name: string
    other_boards: string[]
  }>
  recent_subsidiaries: Array<{
    name: string
    jurisdiction: string | null
  }>
  insider_trades: Array<{
    insider_name: string
    insider_title: string
    transaction_date: string
    transaction_code: string
    transaction_type: string
    security_title: string
    shares: number
    price_per_share: number
    total_value: number
    filing_date: string
    accession_number: string
  }>
  insider_trade_summary: {
    total: number
    unique_insiders: number
    purchases: number
    sales: number
  } | null
}

export interface ProfileSearchResult {
  cik: string
  name: string
  ticker: string | null
  signal_count: number
}

export interface InsightItem {
  category: string
  headline: string
  description: string
  entities: Array<{ type: string; name: string; cik?: string }>
  importance: string
}

// Market Scan types
export interface MarketScanStatus {
  status: 'idle' | 'in_progress' | 'completed' | 'error' | 'started' | 'already_running'
  companies_discovered: number
  companies_scanned: number
  events_stored: number
  errors_count: number
  message: string
}

// Stock Price types
export interface StockPriceData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface StockPriceResponse {
  ticker: string
  period: string
  count: number
  prices: StockPriceData[]
}

export interface TopInsiderActivity {
  cik: string
  company_name: string
  ticker: string | null
  trade_count: number
  unique_insiders: number
  total_buy_value: number
  total_sell_value: number
  net_direction: 'buying' | 'selling' | 'mixed'
}

// Stock Price API
export const stockPriceApi = {
  getPrice: (ticker: string, period = '1y') =>
    api.get<StockPriceResponse>(`/stock-price/${ticker}`, { params: { period } }),
}

// Feed API
export const feedApi = {
  getFeed: (days = 30, limit = 50, minLevel = 'low', cik?: string) =>
    api.get<FeedResponse>('/feed', { params: { days, limit, min_level: minLevel, ...(cik ? { cik } : {}) } }),

  getStats: () => api.get<DbStats>('/feed/stats'),

  getSummary: () => api.get<FeedSummary>('/feed/summary'),

  getHighSignals: (days = 30, limit = 20) =>
    api.get<FeedResponse>('/feed/high-signals', { params: { days, limit } }),

  scanCompany: (cik: string, companyName: string, limit = 20) =>
    api.post(`/feed/scan/${cik}`, null, { params: { company_name: companyName, limit } }),

  marketScan: (daysBack = 3) =>
    api.post<{ status: string; message: string }>(`/feed/market-scan`, null, { params: { days_back: daysBack } }),

  marketScanStatus: () =>
    api.get<MarketScanStatus>('/feed/market-scan/status'),

  getTopInsiderActivity: (days = 30, limit = 10) =>
    api.get<TopInsiderActivity[]>('/feed/top-insider-activity', { params: { days, limit } }),
}

// Insider Trades API
export const insiderTradesApi = {
  getTrades: (cik: string, days = 90, limit = 50) =>
    api.get<InsiderTradesResponse>('/insider-trades', { params: { cik, days, limit } }),

  getSummary: (cik: string, days = 90) =>
    api.get<InsiderTradeSummary>('/insider-trades/summary', { params: { cik, days } }),

  scanCompany: (cik: string, companyName: string, limit = 50) =>
    api.post(`/insider-trades/scan/${cik}`, null, { params: { company_name: companyName, limit } }),

  backfill: (maxCompanies?: number) =>
    api.post('/insider-trades/backfill', null, { params: { max_companies: maxCompanies } }),

  backfillStatus: () =>
    api.get('/insider-trades/backfill/status'),
}

// Profile API
export const profileApi = {
  getProfile: (cik: string) => api.get<CompanyProfile>(`/profile/${cik}`),

  searchCompanies: (query: string, limit = 20) =>
    api.get<{ query: string; total: number; results: ProfileSearchResult[] }>('/profile/search/companies', {
      params: { q: query, limit },
    }),

  getSignals: (cik: string, limit = 50) =>
    api.get(`/profile/${cik}/signals`, { params: { limit } }),

  getConnections: (cik: string) => api.get(`/profile/${cik}/connections`),

  getPeople: (cik: string) => api.get(`/profile/${cik}/people`),

  getSubsidiaries: (cik: string, limit = 50) =>
    api.get(`/profile/${cik}/subsidiaries`, { params: { limit } }),
}

// Insights API
export const insightsApi = {
  getInsights: (limit = 50) =>
    api.get<{ total: number; insights: InsightItem[] }>('/insights', { params: { limit } }),

  getSummary: () =>
    api.get<{ total_insights: number; by_category: Record<string, { count: number; high_importance: number }>; top_insights: InsightItem[] }>('/insights/summary'),
}

// Event Detail types
export interface EventDetailItem {
  item_number: string
  item_name: string
  signal_type: string
  raw_text: string
}

export interface CitedParty {
  name: string
  source_quote: string
}

export interface CitedTerm {
  term: string
  source_quote: string
}

export interface EventDetailAnalysis {
  agreement_type: string
  summary: string
  parties_involved: CitedParty[]
  key_terms: CitedTerm[]
  forward_looking: string
  forward_looking_source: string
  market_implications: string
  market_implications_source: string
  cached?: boolean
}

export interface EventTimelineEntry {
  date: string
  type: 'event' | 'trade'
  description: string
  detail: string
  is_current: boolean
  // Event-specific
  accession_number?: string
  signal_level?: string
  // Trade-specific
  trade_type?: 'buy' | 'sell' | 'exercise_hold' | 'exercise_sell' | 'award' | 'tax' | 'disposition' | 'gift' | 'conversion' | 'will' | 'other'
  notable?: boolean
  notable_reasons?: string[]
}

export interface DealConnection {
  cik: string
  name: string
  ticker: string | null
  agreement_type: string
  filing_date: string
  accession_number: string
  source_quote: string
}

export interface CompanyContext {
  sic_description: string | null
  state_of_incorporation: string | null
  officers: Array<{ name: string; title: string | null }>
  directors: Array<{ name: string; other_boards: string[] }>
  board_connections: Array<{ company_name: string; cik: string; shared_directors: string[] }>
  subsidiaries_count: number
}

export interface DecisionCard {
  action: 'BUY' | 'WATCH' | 'PASS'
  conviction: 'HIGH' | 'MEDIUM' | 'LOW'
  one_liner: string
  insider_direction: 'buying' | 'selling' | 'mixed' | 'none'
  days_since_filing: number | null
  price_change_pct?: number
  price_at_filing?: number
  price_current?: number
}

export interface EventDetailResponse {
  event: {
    accession_number: string
    filing_date: string
    signal_level: string
    signal_summary: string
    items: EventDetailItem[]
    item_numbers: string[]
    persons_mentioned: string[]
  }
  analysis: EventDetailAnalysis
  timeline: EventTimelineEntry[]
  deals: DealConnection[]
  company: {
    cik: string
    name: string
    ticker: string | null
  }
  combined_signal_level?: string
  insider_context?: InsiderContextData | null
  decision_card?: DecisionCard
  company_context?: CompanyContext | null
  signal_type?: 'insider_cluster' | '8k'
  cluster_detail?: ClusterDetail
}

// Event Detail API
export const eventDetailApi = {
  getDetail: (accessionNumber: string) =>
    api.get<EventDetailResponse>(`/event-detail/${accessionNumber}`),
}

// Citation types
export interface Citation {
  fact_type: string
  entity_name: string
  related_entity: string
  fact_value: string | null
  raw_text: string | null
  section_name: string | null
  table_name: string | null
  confidence: number
  extraction_method: string
  filing_accession: string
  filing_type: string
  filing_date: string | null
  filing_url: string | null
}

export interface CitationSummary {
  total_citations: number
  filing_types: string[]
  date_range: [string, string] | null
  avg_confidence: number
  extraction_methods: string[]
}

export interface CitationVerification {
  entity_id: string
  total_facts: number
  verified: number
  partial: number
  unverified: number
  verification_rate: number
  facts: Array<{
    rel_type: string
    target_name: string
    confidence: number
    extraction_method: string
    has_raw_text: boolean
    has_section: boolean
    verification_status: string
  }>
}

// Citations API
export const citationsApi = {
  getEntityCitations: (entityId: string, limit = 50, factType?: string) =>
    api.get<Citation[]>(`/citations/entity/${entityId}`, {
      params: { limit, fact_type: factType },
    }),

  getSummary: (entityId: string) =>
    api.get<CitationSummary>(`/citations/summary/${entityId}`),

  verify: (entityId: string, minConfidence = 0.8) =>
    api.get<CitationVerification>(`/citations/verify/${entityId}`, {
      params: { min_confidence: minConfidence },
    }),

  getFilingCitations: (accessionNumber: string, limit = 100) =>
    api.get(`/citations/filing/${accessionNumber}`, { params: { limit } }),

  getRelationshipCitation: (relType: string, fromId: string, toId: string) =>
    api.get(`/citations/relationship/${relType}/${fromId}/${toId}`),
}

// Evidence Chain types
export interface EvidenceStep {
  step: number
  fact: string
  claim_type: 'direct' | 'computed' | 'inferred'
  source_type: string
  filing_url: string | null
  filing_type: string | null
  filing_accession: string | null
  filing_date: string | null
  source_section: string | null
  raw_text: string
  raw_text_hash: string
  confidence: number
  extraction_method: string | null
}

export interface EvidenceChain {
  claim: string
  claim_type: 'direct' | 'computed' | 'inferred'
  overall_confidence: number
  evidence_steps: EvidenceStep[]
  graph_path: string | null
  generated_at: string
}

export interface ConnectionClaim {
  entity_a_id: string
  entity_a_name: string
  entity_b_id: string
  entity_b_name: string
  connection_type: string
  claim: string
  claim_type: 'direct' | 'computed' | 'inferred'
  evidence_chain: EvidenceChain
  path_length: number
}

export interface RiskFactor {
  factor_name: string
  factor_description: string
  weight: number
  source_type: string
  filing_url: string | null
  filing_type: string | null
  raw_text: string | null
  confidence: number
}

export interface RiskAssessment {
  entity_id: string
  entity_name: string | null
  risk_score: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  factor_count: number
  risk_factors: RiskFactor[]
  evidence_chain: EvidenceChain
  assessed_at: string
}

export interface SharedConnection {
  shared_entity_id: string
  shared_entity_name: string
  shared_entity_type: string
  connection_to_a: string
  connection_to_b: string
  evidence_a: EvidenceStep
  evidence_b: EvidenceStep
}

export interface SharedConnectionsResult {
  entity_a_id: string
  entity_a_name: string
  entity_b_id: string
  entity_b_name: string
  shared_connections: SharedConnection[]
  total_count: number
}

export interface EntityConnection {
  connected_entity: {
    id: string
    name: string
    type: string
  }
  relationship: string
  details: {
    percentage: number | null
    title: string | null
  }
  citation: {
    filing_url: string | null
    filing_type: string | null
    filing_accession: string | null
    filing_date: string | null
    source_section: string | null
    raw_text: string | null
    confidence: number | null
    extraction_method: string | null
  }
}

export interface VerificationResult {
  entity_id: string
  total_claims: number
  verified_count: number
  partial_count: number
  unverified_count: number
  verification_rate: number
  verified: Array<{
    connected_entity: string
    relationship: string
    confidence: number
    has_raw_text: boolean
    filing_accession: string | null
    status: string
  }>
  partial: Array<{
    connected_entity: string
    relationship: string
    confidence: number
    has_raw_text: boolean
    filing_accession: string | null
    status: string
  }>
  unverified: Array<{
    connected_entity: string
    relationship: string
    confidence: number
    has_raw_text: boolean
    filing_accession: string | null
    status: string
  }>
}

// Connections API
export const connectionsApi = {
  findConnection: (entityA: string, entityB: string, maxHops = 4, byName = false) =>
    api.get<ConnectionClaim>('/connections/find', {
      params: { entity_a: entityA, entity_b: entityB, max_hops: maxHops, by_name: byName },
    }),

  findSharedConnections: (entityAId: string, entityBId: string, limit = 20) =>
    api.get<SharedConnectionsResult>('/connections/shared', {
      params: { entity_a: entityAId, entity_b: entityBId, limit },
    }),

  getRiskAssessment: (entityId: string) =>
    api.get<RiskAssessment>(`/connections/risk/${entityId}`),

  getRiskSummary: (entityId: string) =>
    api.get<{ entity_id: string; entity_name: string; risk_score: number; risk_level: string; factor_count: number; top_factors: string[] }>(`/connections/risk/${entityId}/summary`),

  getEntityConnections: (entityId: string, limit = 50) =>
    api.get<{ entity_id: string; total_connections: number; connections_by_type: Record<string, EntityConnection[]>; connections: EntityConnection[] }>(`/connections/entity/${entityId}`, {
      params: { limit },
    }),

  verifyEntity: (entityId: string, limit = 50) =>
    api.get<VerificationResult>(`/connections/verify/${entityId}`, {
      params: { limit },
    }),
}

export default api
