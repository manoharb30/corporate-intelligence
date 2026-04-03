import { useEffect, useState, useRef, useCallback } from 'react'
import { feedApi, profileApi, anomaliesApi, SignalItem, ProfileSearchResult, MarketScanStatus, TopInsiderActivity, CompanyFilter, AnomalyItem } from '../services/api'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import SignalCard from '../components/SignalCard'

type SignalLevel = 'all' | 'critical' | 'high' | 'medium' | 'low'
type FeedTab = 'trade' | 'intelligence'

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`
  return `$${v.toFixed(0)}`
}

export default function Feed() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const cikFilter = searchParams.get('cik')
  const tabParam = searchParams.get('tab') as FeedTab | null
  const [activeTab, setActiveTab] = useState<FeedTab>(tabParam === 'intelligence' ? 'intelligence' : 'trade')
  const [signals, setSignals] = useState<SignalItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filterLevel, setFilterLevel] = useState<SignalLevel>('all')
  const [days, setDays] = useState(cikFilter ? 90 : 30)
  const [, setByLevel] = useState({ high: 0, medium: 0, low: 0 })
  const [, setByCombined] = useState({ critical: 0, high_bearish: 0, high: 0, medium: 0, low: 0 })
  const [companyFilter, setCompanyFilter] = useState<CompanyFilter | null>(null)
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([])

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ProfileSearchResult[]>([])
  const [searching, setSearching] = useState(false)

  // Insider activity state
  const [insiderActivity, setInsiderActivity] = useState<TopInsiderActivity[]>([])

  // Market scan state
  const [scanStatus, setScanStatus] = useState<MarketScanStatus | null>(null)
  const [scanBanner, setScanBanner] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Sync tab with URL
  useEffect(() => {
    if (tabParam === 'intelligence' || tabParam === 'trade') {
      setActiveTab(tabParam)
    }
  }, [tabParam])

  const handleTabChange = (tab: FeedTab) => {
    setActiveTab(tab)
    const params = new URLSearchParams(searchParams)
    params.set('tab', tab)
    setSearchParams(params, { replace: true })
  }

  useEffect(() => {
    let ignore = false
    const fetchFeed = async () => {
      setLoading(true)
      try {
        // Try precomputed feed first (instant) — only when no CIK filter
        if (!cikFilter) {
          try {
            const [preRes, insiderRes, anomalyRes] = await Promise.allSettled([
              feedApi.getPrecomputed(),
              feedApi.getTopInsiderActivity(30, 10),
              anomaliesApi.getTop(50),
            ])
            if (ignore) return
            if (preRes.status === 'fulfilled' && preRes.value.data.signals?.length > 0) {
              setSignals(preRes.value.data.signals)
              if (preRes.value.data.by_level) setByLevel(preRes.value.data.by_level)
              if (preRes.value.data.by_combined) setByCombined(preRes.value.data.by_combined)
              if (insiderRes.status === 'fulfilled' && insiderRes.value) setInsiderActivity((insiderRes.value as any).data)
              if (anomalyRes.status === 'fulfilled') setAnomalies(anomalyRes.value.data.anomalies)
              return
            }
          } catch {
            // Fall through to live fetch
          }
        }
        // Fallback: live feed (when precomputed unavailable or CIK filter active)
        const [feedRes, insiderRes, anomalyRes] = await Promise.allSettled([
          feedApi.getFeed(days, 100, 'medium', cikFilter || undefined),
          cikFilter ? Promise.resolve(null) : feedApi.getTopInsiderActivity(30, 10),
          anomaliesApi.getTop(50),
        ])
        if (ignore) return
        if (feedRes.status === 'fulfilled') {
          setSignals(feedRes.value.data.signals)
          setByLevel(feedRes.value.data.by_level)
          if (feedRes.value.data.by_combined) setByCombined(feedRes.value.data.by_combined)
          setCompanyFilter(feedRes.value.data.company_filter || null)
        }
        if (insiderRes.status === 'fulfilled' && insiderRes.value) setInsiderActivity((insiderRes.value as any).data)
        if (anomalyRes.status === 'fulfilled') setAnomalies(anomalyRes.value.data.anomalies)
      } catch (error) {
        if (!ignore) console.error('Failed to load feed:', error)
      } finally {
        if (!ignore) setLoading(false)
      }
    }
    fetchFeed()
    return () => { ignore = true }
  }, [days, cikFilter])

  useEffect(() => {
    if (searchQuery.length >= 2) {
      const timer = setTimeout(() => searchCompanies(searchQuery), 300)
      return () => clearTimeout(timer)
    } else {
      setSearchResults([])
    }
  }, [searchQuery])

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }, [])

  const startPolling = useCallback(() => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const res = await feedApi.marketScanStatus()
        const status = res.data
        setScanStatus(status)
        if (status.status === 'completed') {
          stopPolling()
          setScanBanner(`Scan Complete - ${status.companies_scanned} companies, ${status.events_stored} events`)
          refreshFeed()
        } else if (status.status === 'error') {
          stopPolling()
          setScanBanner(`Scan Error: ${status.message}`)
        }
      } catch { stopPolling() }
    }, 3000)
  }, [stopPolling])

  const handleMarketScan = async () => {
    try {
      setScanBanner(null)
      const res = await feedApi.marketScan(3)
      if (res.data.status === 'already_running') { startPolling(); return }
      setScanStatus({ status: 'in_progress', companies_discovered: 0, companies_scanned: 0, events_stored: 0, errors_count: 0, message: 'Starting...' })
      startPolling()
    } catch { setScanBanner('Failed to start scan') }
  }

  const refreshFeed = async () => {
    setLoading(true)
    try {
      const [feedRes, insiderRes] = await Promise.allSettled([
        feedApi.getFeed(days, 100, 'low', cikFilter || undefined),
        cikFilter ? Promise.resolve(null) : feedApi.getTopInsiderActivity(30, 10),
      ])
      if (feedRes.status === 'fulfilled') {
        setSignals(feedRes.value.data.signals)
        setByLevel(feedRes.value.data.by_level)
        if (feedRes.value.data.by_combined) setByCombined(feedRes.value.data.by_combined)
        setCompanyFilter(feedRes.value.data.company_filter || null)
      }
      if (insiderRes.status === 'fulfilled' && insiderRes.value) setInsiderActivity((insiderRes.value as any).data)
    } catch (error) {
      console.error('Failed to load feed:', error)
    } finally {
      setLoading(false)
    }
  }

  const searchCompanies = async (query: string) => {
    setSearching(true)
    try {
      const response = await profileApi.searchCompanies(query, 10)
      setSearchResults(response.data.results)
    } catch { /* ignore */ } finally {
      setSearching(false)
    }
  }

  // Trade tab: cluster + sell cluster + compound-with-cluster
  const tradeSignals = signals.filter(s =>
    s.signal_type === 'insider_cluster' ||
    s.signal_type === 'insider_sell_cluster' ||
    s.signal_type === 'compound'
  )

  // Intelligence tab: 8-K based signals
  const intelligenceSignals = signals.filter(s =>
    s.signal_type === '8k' || (!s.signal_type)
  )

  const activeSignals = activeTab === 'trade' ? tradeSignals : intelligenceSignals

  const filteredSignals = filterLevel === 'all'
    ? activeSignals
    : filterLevel === 'critical'
    ? activeSignals.filter(s => s.combined_signal_level === 'critical')
    : activeSignals.filter(s => s.signal_level === filterLevel || s.combined_signal_level === filterLevel)

  // Recompute counts based on active tab signals
  const tabByLevel = {
    high: activeSignals.filter(s => s.signal_level === 'high').length,
    medium: activeSignals.filter(s => s.signal_level === 'medium').length,
    low: activeSignals.filter(s => s.signal_level === 'low').length,
  }
  const tabCritical = activeSignals.filter(s => s.combined_signal_level === 'critical').length

  const filterPills: { key: SignalLevel; label: string; count: number; color: string; activeColor: string }[] = [
    { key: 'all', label: 'All', count: activeSignals.length, color: 'bg-gray-100 text-gray-700', activeColor: 'bg-primary-600 text-white' },
    { key: 'critical', label: 'Critical', count: tabCritical, color: 'bg-purple-50 text-purple-700', activeColor: 'bg-purple-600 text-white' },
    { key: 'high', label: 'High', count: tabByLevel.high, color: 'bg-red-50 text-red-700', activeColor: 'bg-red-500 text-white' },
    { key: 'medium', label: 'Medium', count: tabByLevel.medium, color: 'bg-yellow-50 text-yellow-700', activeColor: 'bg-yellow-500 text-white' },
    { key: 'low', label: 'Low', count: tabByLevel.low, color: 'bg-blue-50 text-blue-700', activeColor: 'bg-blue-500 text-white' },
  ]

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {activeTab === 'trade' ? 'Trade Signals' : 'Event Intelligence'}
          </h1>
          <p className="text-sm text-gray-600">
            {activeTab === 'trade'
              ? 'Insider cluster alerts and compound signals'
              : 'SEC 8-K filings with insider behavior analysis'}
          </p>
        </div>
        <button
          onClick={handleMarketScan}
          disabled={true}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium"
        >
          {scanStatus?.status === 'in_progress' && (
            <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
          )}
          Scan Market
        </button>
      </div>

      {/* Tab toggle */}
      {!cikFilter && (
        <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
          <button
            onClick={() => handleTabChange('trade')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${
              activeTab === 'trade'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${activeTab === 'trade' ? 'bg-green-500' : 'bg-gray-300'}`}></span>
            Trade Signals
            <span className="text-xs text-gray-400">({tradeSignals.length})</span>
          </button>
          <button
            onClick={() => handleTabChange('intelligence')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${
              activeTab === 'intelligence'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${activeTab === 'intelligence' ? 'bg-purple-500' : 'bg-gray-300'}`}></span>
            Event Intelligence
            <span className="text-xs text-gray-400">({intelligenceSignals.length})</span>
          </button>
        </div>
      )}

      {/* Scan Progress */}
      {scanStatus?.status === 'in_progress' && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-blue-800">{scanStatus.message}</span>
            <span className="text-blue-600">
              {scanStatus.companies_discovered > 0 ? `${scanStatus.companies_scanned}/${scanStatus.companies_discovered}` : 'Discovering...'}
            </span>
          </div>
          {scanStatus.companies_discovered > 0 && (
            <div className="w-full bg-blue-200 rounded-full h-1.5 mt-2">
              <div className="bg-blue-600 h-1.5 rounded-full transition-all" style={{ width: `${(scanStatus.companies_scanned / scanStatus.companies_discovered) * 100}%` }}></div>
            </div>
          )}
        </div>
      )}

      {scanBanner && (
        <div className={`mb-4 p-3 rounded-lg flex items-center justify-between text-sm ${
          scanBanner.includes('Error') || scanBanner.includes('Failed') ? 'bg-red-50 border border-red-200 text-red-800' : 'bg-green-50 border border-green-200 text-green-800'
        }`}>
          <span className="font-medium">{scanBanner}</span>
          <button onClick={() => setScanBanner(null)} className="opacity-60 hover:opacity-100 ml-4">Dismiss</button>
        </div>
      )}

      {/* Company filter header */}
      {companyFilter && (
        <div className="mb-4 p-4 bg-white rounded-lg border border-gray-200 shadow-sm flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              {companyFilter.name}
              {companyFilter.ticker && <span className="text-gray-500 ml-2">({companyFilter.ticker})</span>}
            </h2>
            <p className="text-sm text-gray-600">All signals for this company</p>
          </div>
          <Link to="/signals" className="text-sm text-primary-600 hover:underline font-medium">
            Clear filter
          </Link>
        </div>
      )}

      {/* Sticky filter bar */}
      <div className="sticky top-0 z-10 bg-gray-50 -mx-4 px-4 py-3 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 border-b border-gray-200 mb-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          {/* Signal level pills */}
          <div className="flex gap-2">
            {filterPills.map(pill => (
              <button
                key={pill.key}
                onClick={() => setFilterLevel(pill.key)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  filterLevel === pill.key ? pill.activeColor : pill.color + ' hover:opacity-80'
                }`}
              >
                {pill.label} ({pill.count})
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            {/* Time range */}
            <div className="flex gap-1">
              {[7, 30, 60, 90].map(d => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className={`px-2.5 py-1 rounded text-xs font-medium ${
                    days === d ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {d}d
                </button>
              ))}
            </div>

            {/* Search (hidden when filtered by company) */}
            {!cikFilter && (
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="w-48 px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                />
                {searching && (
                  <div className="absolute right-2 top-2">
                    <div className="animate-spin h-3 w-3 border-2 border-primary-500 border-t-transparent rounded-full"></div>
                  </div>
                )}
                {searchResults.length > 0 && (
                  <div className="absolute top-full right-0 mt-1 w-72 bg-white rounded-lg shadow-xl border border-gray-200 z-50 max-h-64 overflow-y-auto">
                    {searchResults.map(r => (
                      <button
                        key={r.cik}
                        onClick={() => { navigate(`/company/${r.cik}`); setSearchQuery(''); setSearchResults([]) }}
                        className="w-full text-left px-3 py-2 hover:bg-gray-50 text-sm border-b border-gray-100 last:border-0"
                      >
                        <span className="font-medium text-gray-900">{r.name}</span>
                        {r.ticker && <span className="text-gray-500 ml-1">({r.ticker})</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Signal list */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin h-8 w-8 border-4 border-primary-500 border-t-transparent rounded-full"></div>
        </div>
      ) : activeTab === 'intelligence' && !cikFilter ? (
        /* Intelligence tab: signal cards + anomaly context */
        <>
          {filteredSignals.length === 0 ? (
            <div className="text-center py-12 text-gray-500">No event intelligence signals found for the selected filters</div>
          ) : (
            <div className="space-y-3">
              {filteredSignals.map((signal, idx) => (
                <SignalCard key={`${signal.accession_number}-${idx}`} signal={signal} />
              ))}
            </div>
          )}

          {/* Anomaly summary at bottom of intelligence tab */}
          {anomalies.length > 0 && (
            <div className="mt-8 bg-purple-50 border border-purple-200 rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Pre-Filing Insider Activity</h3>
                  <p className="text-sm text-gray-600">Companies where insiders sold heavily before material SEC filings</p>
                </div>
                <a
                  href={anomaliesApi.getDownloadUrl()}
                  download
                  className="px-3 py-1.5 text-xs font-medium text-purple-600 bg-white border border-purple-300 rounded-lg hover:bg-purple-50"
                >
                  Download CSV
                </a>
              </div>
              <div className="bg-white rounded-lg border border-purple-100 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-purple-50/50">
                      <th className="text-left px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Company</th>
                      <th className="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase">Event</th>
                      <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500 uppercase">Pre-Event Selling</th>
                      <th className="text-right px-3 py-2 text-xs font-semibold text-gray-500 uppercase">Lead Time</th>
                      <th className="text-right px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Ratio</th>
                    </tr>
                  </thead>
                  <tbody>
                    {anomalies.slice(0, 10).map((a, idx) => {
                      const eventLabel =
                        a.event_type === 'material_agreement' ? 'Material Agmt' :
                        a.event_type === 'executive_change' ? 'Exec Change' :
                        a.event_type === 'governance_change' ? 'Governance' :
                        a.event_type === 'acquisition_disposition' ? 'Acquisition' :
                        a.event_type
                      return (
                        <tr
                          key={`${a.cik}-${idx}`}
                          onClick={() => navigate(`/signal/${encodeURIComponent(a.accession_number)}`)}
                          className="border-b border-gray-50 hover:bg-purple-50/30 cursor-pointer"
                        >
                          <td className="px-4 py-2">
                            <span className="font-bold text-gray-900">{a.ticker || '—'}</span>
                            <span className="text-gray-500 ml-2 text-xs truncate">{a.company_name}</span>
                          </td>
                          <td className="px-3 py-2 text-xs text-gray-600">{eventLabel}</td>
                          <td className="px-3 py-2 text-right font-semibold text-red-600">{formatVolume(a.pre_event_sell_value)}</td>
                          <td className="px-3 py-2 text-right text-gray-600">
                            {a.avg_days_before_event !== null ? `${Math.round(a.avg_days_before_event)}d` : '—'}
                          </td>
                          <td className="px-4 py-2 text-right">
                            <span className="text-xs font-medium text-purple-700">{(a.ratio * 100).toFixed(0)}%</span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      ) : filteredSignals.length === 0 ? (
        <div className="text-center py-12 text-gray-500">No signals found for the selected filters</div>
      ) : (
        <div className="space-y-3">
          {filteredSignals.map((signal, idx) => (
            <SignalCard key={`${signal.accession_number}-${idx}`} signal={signal} />
          ))}
        </div>
      )}

      {/* Top Insider Activity */}
      {activeTab === 'trade' && insiderActivity.length > 0 && (
        <div className="mt-8 bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Top Insider Activity (30d)</h2>
          <div className="space-y-2">
            {insiderActivity.map((item, idx) => (
              <Link
                key={idx}
                to={`/company/${item.cik}`}
                className="flex items-center justify-between p-2.5 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900 truncate">{item.company_name}</span>
                    {item.ticker && <span className="text-xs text-gray-500">({item.ticker})</span>}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {item.trade_count} trades by {item.unique_insiders} insider{item.unique_insiders !== 1 ? 's' : ''}
                  </div>
                </div>
                <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${
                  item.net_direction === 'buying' ? 'text-green-700 bg-green-50 border border-green-200' :
                  item.net_direction === 'selling' ? 'text-red-700 bg-red-50 border border-red-200' :
                  'text-gray-600 bg-gray-100 border border-gray-200'
                }`}>
                  {item.net_direction === 'buying' ? 'Net Buy' :
                   item.net_direction === 'selling' ? 'Net Sell' : 'Mixed'}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
