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

export default api
