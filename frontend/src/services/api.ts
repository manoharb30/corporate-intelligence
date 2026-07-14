import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// ============ Snapshot (Signal List) ============

export interface SnapshotSignal {
  ticker: string
  company_name: string
  cik: string
  signal_date: string
  num_insiders: number
  total_value: number
  accession_number: string
  conviction_tier?: 'strong_buy' | 'buy' | 'watch'
  return_pct: number
  spy_return_pct?: number | null
  alpha_pct?: number | null
  days_held: number
}

export interface WeeklySnapshot {
  period_days: number
  generated_at: string
  total_signals: number
  signals: SnapshotSignal[]
}

export const snapshotApi = {
  getWeekly: (days = 30, date?: string) =>
    api.get<WeeklySnapshot>('/snapshot/weekly', {
      params: { days, ...(date ? { date } : {}) },
    }),
}

// ============ Event Detail (Signal Detail) ============

export interface ClusterBuyerDetail {
  name: string
  title: string
  total_value: number
  trade_count: number
  total_shares: number
  avg_price_per_share: number | null
  trade_dates: string[]
  form4_url?: string
}

export interface ClusterDetail {
  window_start: string
  window_end: string
  num_buyers: number
  buyers: ClusterBuyerDetail[]
  direction?: 'buy' | 'sell'
}

export interface EventDetailResponse {
  event: {
    accession_number: string
    filing_date: string
    signal_level: string
    signal_summary: string
  }
  timeline: Array<{
    date: string
    type: 'event' | 'trade'
    description: string
    detail: string
    is_current: boolean
    notable?: boolean
    form4_url?: string
  }>
  company: {
    cik: string
    name: string
    ticker: string | null
  }
  signal_type?: 'insider_cluster'  // v1.3: insider_sell_cluster removed
  cluster_detail?: ClusterDetail
  has_hostile_activist?: boolean
  hostile_keywords?: string[]
}

export const eventDetailApi = {
  getDetail: (accessionNumber: string) =>
    api.get<EventDetailResponse>(`/event-detail/${accessionNumber}`),
}

// ============ Signal Performance (Performance Tracker) ============

export interface SignalPerf {
  signal_id: string
  ticker: string
  company_name: string
  cik: string
  signal_date: string
  actionable_date: string | null
  direction: 'buy' | 'sell'
  signal_level: string
  num_insiders: number
  total_value: number
  conviction_tier: string
  industry: string | null
  price_day0: number | null
  price_day1: number | null
  price_day2: number | null
  price_day3: number | null
  price_day5: number | null
  price_day7: number | null
  price_day90: number | null
  price_current: number | null
  price_current_date: string | null
  return_current: number | null
  return_day0: number | null
  return_day1: number | null
  return_day2: number | null
  return_day3: number | null
  return_day5: number | null
  return_day7: number | null
  spy_return_90d: number | null
  is_mature: boolean
  market_cap: number | null
  pct_of_mcap: number | null
}

export interface DashboardStats {
  total_signals: number
  wins: number
  losses: number
  hit_rate: number
  avg_return: number
  avg_alpha: number
  beat_spy_pct: number
  computed_at: string
}

export const signalPerfApi = {
  getAll: (direction?: string, matureOnly = false, meaningfulOnly = false, limit = 500) =>
    api.get<SignalPerf[]>('/signal-performance', {
      params: { direction, mature_only: matureOnly, meaningful_only: meaningfulOnly, limit },
    }),
  getDashboardStats: () =>
    api.get<DashboardStats>('/signal-performance/dashboard-stats'),
  getDownloadUrl: (direction?: string, meaningfulOnly = true) =>
    `/api/signal-performance/download?mature_only=true&meaningful_only=${meaningfulOnly}${direction ? '&direction=' + direction : ''}`,
}

// ============ Portfolio (Alpaca paper account) ============

export interface PortfolioPosition {
  ticker: string
  company_name: string | null
  qty: number
  avg_fill: number
  last_price: number
  market_value: number
  cost_basis: number
  unrealized_pl: number
  unrealized_plpc: number
  signal_date: string | null
  day0_price: number | null
  shortfall_pct: number | null
  num_insiders: number | null
  cluster_value: number | null
  exit_date: string | null
  days_left: number | null
}

export interface PortfolioSweep {
  ticker: string
  qty: number
  market_value: number
  unrealized_pl: number
}

export interface PortfolioActivity {
  time: string
  symbol: string
  side: string
  qty: number
  price: number
  type: 'sweep' | 'order'
}

export interface PortfolioSnapshot {
  configured: boolean
  as_of?: string
  account?: {
    value: number
    cash: number
    initial_capital: number
    pnl: number
    pnl_pct: number
    position_slice: number
  }
  allocation?: { positions_pct: number; sweep_pct: number; cash_pct: number }
  positions?: PortfolioPosition[]
  positions_value?: number
  avg_shortfall_pct?: number | null
  sweep?: PortfolioSweep | null
  equity_curve?: { date: string; equity: number }[]
  activities?: PortfolioActivity[]
}

export const portfolioApi = {
  getSnapshot: () => api.get<PortfolioSnapshot>('/portfolio'),
}

export default api
