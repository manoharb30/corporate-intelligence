import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { feedApi, insightsApi, profileApi, DbStats, SignalItem, InsightItem, TopInsiderActivity, ProfileSearchResult } from '../services/api'
import SignalCard from '../components/SignalCard'
import StatCard from '../components/StatCard'

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<DbStats | null>(null)
  const [topSignals, setTopSignals] = useState<SignalItem[]>([])
  const [insights, setInsights] = useState<InsightItem[]>([])
  const [insiderActivity, setInsiderActivity] = useState<TopInsiderActivity[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ProfileSearchResult[]>([])
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [statsRes, feedRes, insightsRes, insiderRes] = await Promise.allSettled([
        feedApi.getStats(),
        feedApi.getFeed(90, 8, 'medium'),
        insightsApi.getSummary(),
        feedApi.getTopInsiderActivity(30, 8),
      ])

      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
      if (feedRes.status === 'fulfilled') setTopSignals(feedRes.value.data.signals)
      if (insightsRes.status === 'fulfilled') {
        const data = insightsRes.value.data as any
        setInsights(data.insights || data.top_insights || [])
      }
      if (insiderRes.status === 'fulfilled') setInsiderActivity(insiderRes.value.data)
    } catch (error) {
      console.error('Failed to load dashboard:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (searchQuery.length < 2) {
      setSearchResults([])
      return
    }
    const timeout = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await profileApi.searchCompanies(searchQuery, 8)
        setSearchResults(res.data.results)
      } catch {
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 300)
    return () => clearTimeout(timeout)
  }, [searchQuery])

  // Count critical/high signals
  const criticalCount = topSignals.filter(s =>
    s.combined_signal_level === 'critical' || s.combined_signal_level === 'high_bearish'
  ).length
  const highCount = topSignals.filter(s =>
    s.combined_signal_level === 'high' || s.signal_level === 'high'
  ).length

  const getInsightCategoryColor = (category: string) => {
    switch (category.toLowerCase()) {
      case 'board_interlock': return 'bg-purple-100 text-purple-800'
      case 'hub_company': return 'bg-blue-100 text-blue-800'
      case 'bridge_person': return 'bg-green-100 text-green-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full"></div>
      </div>
    )
  }

  return (
    <div>
      {/* Hero */}
      <div className="bg-gradient-to-r from-gray-900 to-primary-900 rounded-xl p-6 mb-6 text-white">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold mb-1">Corporate Intelligence</h1>
            <p className="text-gray-300 text-sm">SEC EDGAR M&A signal detection with insider intelligence</p>
            <div className="flex items-center gap-4 mt-4">
              {criticalCount > 0 && (
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 bg-purple-600 rounded text-sm font-bold animate-pulse">
                    {criticalCount} CRITICAL
                  </span>
                  <span className="text-gray-400 text-sm">signals (90d)</span>
                </div>
              )}
              {highCount > 0 && (
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 bg-red-500 rounded text-sm font-bold">
                    {highCount} HIGH
                  </span>
                  <span className="text-gray-400 text-sm">signals (90d)</span>
                </div>
              )}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold">{stats?.companies.toLocaleString() || 0}</div>
              <div className="text-xs text-gray-400">Companies</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{stats?.events.toLocaleString() || 0}</div>
              <div className="text-xs text-gray-400">Events</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{stats?.insider_transactions.toLocaleString() || 0}</div>
              <div className="text-xs text-gray-400">Insider Trades</div>
            </div>
          </div>
        </div>

        {/* Search bar */}
        <div className="relative mt-5">
          <input
            type="text"
            placeholder="Search companies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-2.5 rounded-lg bg-white/10 border border-white/20 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-400 focus:bg-white/15"
          />
          {searching && (
            <div className="absolute right-3 top-3">
              <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
            </div>
          )}
          {searchResults.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-lg shadow-xl border border-gray-200 z-50 max-h-64 overflow-y-auto">
              {searchResults.map(r => (
                <button
                  key={r.cik}
                  onClick={() => {
                    navigate(`/company/${r.cik}`)
                    setSearchQuery('')
                    setSearchResults([])
                  }}
                  className="w-full text-left px-4 py-2.5 hover:bg-gray-50 flex items-center justify-between border-b border-gray-100 last:border-0"
                >
                  <div>
                    <span className="text-sm font-medium text-gray-900">{r.name}</span>
                    {r.ticker && <span className="text-sm text-gray-500 ml-2">({r.ticker})</span>}
                  </div>
                  {r.signal_count > 0 && (
                    <span className="text-xs text-gray-400">{r.signal_count} signals</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <StatCard label="Persons" value={stats.persons} accent="text-purple-600" />
          <StatCard label="Total Nodes" value={stats.total_nodes} accent="text-gray-800" />
          <StatCard label="Relationships" value={stats.total_relationships} accent="text-gray-800" />
          <StatCard label="Jurisdictions" value={stats.jurisdictions} accent="text-green-600" />
        </div>
      )}

      {/* Active Signals Grid */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-900">Active Signals</h2>
          <Link to="/signals" className="text-sm text-primary-600 hover:underline">View all &rarr;</Link>
        </div>
        {topSignals.length === 0 ? (
          <p className="text-sm text-gray-500">No active signals in the last 90 days</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {topSignals.slice(0, 8).map((signal, idx) => (
              <SignalCard key={`${signal.accession_number}-${idx}`} signal={signal} />
            ))}
          </div>
        )}
      </div>

      {/* Two-column: Network Alerts | Top Insider Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Network Alerts (Insights) */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Network Alerts</h2>
          {insights.length === 0 ? (
            <p className="text-sm text-gray-500">No patterns discovered yet.</p>
          ) : (
            <div className="space-y-2.5">
              {insights.slice(0, 6).map((insight, idx) => (
                <div key={idx} className="p-2.5 rounded-lg bg-gray-50">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${getInsightCategoryColor(insight.category)}`}>
                      {insight.category.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-gray-900">{insight.headline}</p>
                  <p className="text-xs text-gray-600 mt-0.5">{insight.description}</p>
                  {insight.entities?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {insight.entities.slice(0, 3).map((entity, eidx) =>
                        entity.cik ? (
                          <Link key={eidx} to={`/company/${entity.cik}`} className="text-xs text-primary-600 hover:underline">
                            {entity.name}
                          </Link>
                        ) : (
                          <span key={eidx} className="text-xs text-gray-500">{entity.name}</span>
                        )
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top Insider Activity */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Top Insider Activity (30d)</h2>
          {insiderActivity.length === 0 ? (
            <p className="text-sm text-gray-500">No insider trading data available.</p>
          ) : (
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
          )}
        </div>
      </div>
    </div>
  )
}
