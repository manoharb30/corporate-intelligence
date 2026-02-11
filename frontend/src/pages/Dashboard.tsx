import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { feedApi, insightsApi, DbStats, SignalItem, InsightItem } from '../services/api'

export default function Dashboard() {
  const [stats, setStats] = useState<DbStats | null>(null)
  const [topSignals, setTopSignals] = useState<SignalItem[]>([])
  const [insights, setInsights] = useState<InsightItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAll()
  }, [])

  const loadAll = async () => {
    setLoading(true)
    try {
      const [statsRes, feedRes, insightsRes] = await Promise.allSettled([
        feedApi.getStats(),
        feedApi.getFeed(90, 10, 'high'),
        insightsApi.getSummary(),
      ])

      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
      if (feedRes.status === 'fulfilled') setTopSignals(feedRes.value.data.signals)
      if (insightsRes.status === 'fulfilled') {
        // Handle both /insights (returns .insights) and /insights/summary (returns .top_insights)
        const data = insightsRes.value.data as any
        setInsights(data.insights || data.top_insights || [])
      }
    } catch (error) {
      console.error('Failed to load dashboard:', error)
    } finally {
      setLoading(false)
    }
  }

  const getCombinedBadge = (level: string) => {
    switch (level) {
      case 'critical':
        return 'bg-purple-600 animate-pulse'
      case 'high_bearish':
        return 'bg-red-700'
      case 'high':
        return 'bg-red-500'
      case 'medium':
        return 'bg-yellow-500'
      default:
        return 'bg-blue-500'
    }
  }

  const getCombinedLabel = (level: string) => {
    switch (level) {
      case 'critical': return 'CRITICAL'
      case 'high_bearish': return 'HIGH BEARISH'
      default: return level.toUpperCase()
    }
  }

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
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Market Overview</h1>
        <p className="mt-1 text-sm text-gray-600">
          Corporate Intelligence Graph — SEC EDGAR signal detection platform
        </p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <div className="bg-white shadow rounded-lg p-4">
            <div className="text-2xl font-bold text-blue-600">{stats.companies.toLocaleString()}</div>
            <div className="text-sm text-gray-600">Companies</div>
          </div>
          <div className="bg-white shadow rounded-lg p-4">
            <div className="text-2xl font-bold text-red-600">{stats.events.toLocaleString()}</div>
            <div className="text-sm text-gray-600">8-K Events</div>
          </div>
          <div className="bg-white shadow rounded-lg p-4">
            <div className="text-2xl font-bold text-amber-600">{stats.insider_transactions.toLocaleString()}</div>
            <div className="text-sm text-gray-600">Insider Trades</div>
          </div>
          <div className="bg-white shadow rounded-lg p-4">
            <div className="text-2xl font-bold text-purple-600">{stats.persons.toLocaleString()}</div>
            <div className="text-sm text-gray-600">Persons</div>
          </div>
          <div className="bg-white shadow rounded-lg p-4">
            <div className="text-2xl font-bold text-gray-800">{stats.total_nodes.toLocaleString()}</div>
            <div className="text-sm text-gray-600">Total Nodes</div>
          </div>
          <div className="bg-white shadow rounded-lg p-4">
            <div className="text-2xl font-bold text-gray-800">{stats.total_relationships.toLocaleString()}</div>
            <div className="text-sm text-gray-600">Relationships</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Top HIGH Signals */}
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Top Signals (90 days)</h2>
            <Link to="/" className="text-sm text-primary-600 hover:underline">
              View all
            </Link>
          </div>
          {topSignals.length === 0 ? (
            <p className="text-sm text-gray-500">No high-priority signals in the last 90 days</p>
          ) : (
            <div className="space-y-3">
              {topSignals.map((signal, idx) => (
                <div key={`${signal.accession_number}-${idx}`} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase text-white whitespace-nowrap ${getCombinedBadge(signal.combined_signal_level)}`}>
                    {getCombinedLabel(signal.combined_signal_level)}
                  </span>
                  <div className="flex-1 min-w-0">
                    <Link to={`/company/${signal.cik}`} className="font-medium text-gray-900 hover:text-primary-600 text-sm">
                      {signal.company_name}
                    </Link>
                    {signal.ticker && <span className="text-xs text-gray-500 ml-1">({signal.ticker})</span>}
                    <div className="text-xs text-gray-600 mt-0.5">{signal.signal_summary}</div>
                    {signal.insider_context && signal.insider_context.person_matches && signal.insider_context.person_matches.length > 0 && (
                      <div className="text-xs text-yellow-800 mt-1 font-medium bg-yellow-50 px-1.5 py-0.5 rounded">
                        {signal.insider_context.person_matches[0]}
                      </div>
                    )}
                    {signal.insider_context && signal.insider_context.notable_trades.length > 0 && !(signal.insider_context.person_matches?.length) && (
                      <div className="text-xs text-amber-700 mt-1 italic">
                        {signal.insider_context.notable_trades[0]}
                      </div>
                    )}
                  </div>
                  <span className="text-xs text-gray-400 whitespace-nowrap">{signal.filing_date}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Auto-Discovered Patterns (Insights) */}
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Auto-Discovered Patterns</h2>
          </div>
          {insights.length === 0 ? (
            <p className="text-sm text-gray-500">No patterns discovered yet. Run insight analysis to detect board interlocks and hub companies.</p>
          ) : (
            <div className="space-y-3">
              {insights.slice(0, 8).map((insight, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-gray-50">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${getInsightCategoryColor(insight.category)}`}>
                      {insight.category.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs text-gray-400">{insight.importance}</span>
                  </div>
                  <div className="text-sm font-medium text-gray-900">{insight.headline}</div>
                  <div className="text-xs text-gray-600 mt-0.5">{insight.description}</div>
                  {insight.entities && insight.entities.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {insight.entities.slice(0, 3).map((entity, eidx) => (
                        entity.cik ? (
                          <Link key={eidx} to={`/company/${entity.cik}`} className="text-xs text-primary-600 hover:underline">
                            {entity.name}
                          </Link>
                        ) : (
                          <span key={eidx} className="text-xs text-gray-500">{entity.name}</span>
                        )
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mt-8 bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Explore</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link
            to="/"
            className="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-primary-400"
          >
            <div className="flex-1 min-w-0">
              <span className="absolute inset-0" aria-hidden="true" />
              <p className="text-sm font-medium text-gray-900">Signal Feed</p>
              <p className="text-sm text-gray-500">Live M&A signals with insider context</p>
            </div>
          </Link>
          <Link
            to="/intelligence"
            className="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-primary-400"
          >
            <div className="flex-1 min-w-0">
              <span className="absolute inset-0" aria-hidden="true" />
              <p className="text-sm font-medium text-gray-900">Company Intelligence</p>
              <p className="text-sm text-gray-500">Deep-dive into any company</p>
            </div>
          </Link>
          <Link
            to="/graph"
            className="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-primary-400"
          >
            <div className="flex-1 min-w-0">
              <span className="absolute inset-0" aria-hidden="true" />
              <p className="text-sm font-medium text-gray-900">Graph Explorer</p>
              <p className="text-sm text-gray-500">Visualize corporate networks</p>
            </div>
          </Link>
          <Link
            to="/connections"
            className="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-primary-400"
          >
            <div className="flex-1 min-w-0">
              <span className="absolute inset-0" aria-hidden="true" />
              <p className="text-sm font-medium text-gray-900">Connection Finder</p>
              <p className="text-sm text-gray-500">Find paths between entities</p>
            </div>
          </Link>
        </div>
      </div>
    </div>
  )
}
