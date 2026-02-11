import { useEffect, useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { feedApi, profileApi, SignalItem, ProfileSearchResult, MarketScanStatus } from '../services/api'

type SignalLevel = 'all' | 'critical' | 'high' | 'medium' | 'low'

export default function Feed() {
  const [signals, setSignals] = useState<SignalItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filterLevel, setFilterLevel] = useState<SignalLevel>('all')
  const [days, setDays] = useState(30)
  const [byLevel, setByLevel] = useState({ high: 0, medium: 0, low: 0 })
  const [byCombined, setByCombined] = useState({ critical: 0, high_bearish: 0, high: 0, medium: 0, low: 0 })

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ProfileSearchResult[]>([])
  const [searching, setSearching] = useState(false)

  // Market scan state
  const [scanStatus, setScanStatus] = useState<MarketScanStatus | null>(null)
  const [scanBanner, setScanBanner] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    loadFeed()
  }, [days])

  useEffect(() => {
    if (searchQuery.length >= 2) {
      const timer = setTimeout(() => {
        searchCompanies(searchQuery)
      }, 300)
      return () => clearTimeout(timer)
    } else {
      setSearchResults([])
    }
  }, [searchQuery])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
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
          setScanBanner(
            `Market Scan Complete - ${status.companies_scanned} companies scanned, ${status.events_stored} events found`
          )
          loadFeed()
        } else if (status.status === 'error') {
          stopPolling()
          setScanBanner(`Market Scan Error: ${status.message}`)
        }
      } catch {
        stopPolling()
      }
    }, 3000)
  }, [stopPolling])

  const handleMarketScan = async () => {
    try {
      setScanBanner(null)
      const res = await feedApi.marketScan(3)
      if (res.data.status === 'already_running') {
        // Already running, just start polling
        startPolling()
        return
      }
      setScanStatus({
        status: 'in_progress',
        companies_discovered: 0,
        companies_scanned: 0,
        events_stored: 0,
        errors_count: 0,
        message: 'Starting market scan...',
      })
      startPolling()
    } catch (error) {
      console.error('Failed to start market scan:', error)
      setScanBanner('Failed to start market scan')
    }
  }

  const loadFeed = async () => {
    setLoading(true)
    try {
      const response = await feedApi.getFeed(days, 100, 'low')
      setSignals(response.data.signals)
      setByLevel(response.data.by_level)
      if (response.data.by_combined) setByCombined(response.data.by_combined)
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
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setSearching(false)
    }
  }

  const filteredSignals = filterLevel === 'all'
    ? signals
    : filterLevel === 'critical'
    ? signals.filter(s => s.combined_signal_level === 'critical')
    : signals.filter(s => s.signal_level === filterLevel || s.combined_signal_level === filterLevel)

  const getCombinedColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'bg-purple-100 text-purple-900 border-purple-300'
      case 'high_bearish':
        return 'bg-red-100 text-red-900 border-red-300'
      case 'high':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      default:
        return 'bg-blue-100 text-blue-800 border-blue-200'
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

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Signal Feed</h1>
          <p className="mt-1 text-sm text-gray-600">
            M&A signals detected from SEC 8-K filings
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

      {/* Market Scan Progress */}
      {scanStatus?.status === 'in_progress' && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-blue-800">{scanStatus.message}</span>
            <span className="text-sm text-blue-600">
              {scanStatus.companies_discovered > 0
                ? `${scanStatus.companies_scanned}/${scanStatus.companies_discovered}`
                : 'Discovering...'}
            </span>
          </div>
          {scanStatus.companies_discovered > 0 && (
            <div className="w-full bg-blue-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${(scanStatus.companies_scanned / scanStatus.companies_discovered) * 100}%` }}
              ></div>
            </div>
          )}
        </div>
      )}

      {/* Scan Result Banner */}
      {scanBanner && (
        <div className={`mb-6 p-4 rounded-lg flex items-center justify-between ${
          scanBanner.includes('Error') || scanBanner.includes('Failed')
            ? 'bg-red-50 border border-red-200 text-red-800'
            : 'bg-green-50 border border-green-200 text-green-800'
        }`}>
          <span className="text-sm font-medium">{scanBanner}</span>
          <button
            onClick={() => setScanBanner(null)}
            className="text-sm opacity-60 hover:opacity-100 ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Search Bar */}
      <div className="mb-6 relative">
        <input
          type="text"
          placeholder="Search companies by name or ticker..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
        />
        {searchResults.length > 0 && (
          <div className="absolute z-10 w-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-80 overflow-y-auto">
            {searchResults.map((result) => (
              <Link
                key={result.cik}
                to={`/company/${result.cik}`}
                onClick={() => {
                  setSearchQuery('')
                  setSearchResults([])
                }}
                className="block px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-gray-900">{result.name}</span>
                    {result.ticker && (
                      <span className="ml-2 text-sm text-gray-500">({result.ticker})</span>
                    )}
                  </div>
                  <span className="text-sm text-gray-400">
                    {result.signal_count} signals
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
        {searching && (
          <div className="absolute right-3 top-3">
            <div className="animate-spin h-5 w-5 border-2 border-primary-500 border-t-transparent rounded-full"></div>
          </div>
        )}
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <button
          onClick={() => setFilterLevel('all')}
          className={`p-4 rounded-lg border-2 transition-colors ${
            filterLevel === 'all' ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-gray-300'
          }`}
        >
          <div className="text-2xl font-bold text-gray-900">{signals.length}</div>
          <div className="text-sm text-gray-600">Total Signals</div>
        </button>
        <button
          onClick={() => setFilterLevel('critical')}
          className={`p-4 rounded-lg border-2 transition-colors ${
            filterLevel === 'critical' ? 'border-purple-500 bg-purple-50' : 'border-gray-200 hover:border-gray-300'
          }`}
        >
          <div className="text-2xl font-bold text-purple-600">{byCombined.critical}</div>
          <div className="text-sm text-gray-600">Critical</div>
        </button>
        <button
          onClick={() => setFilterLevel('high')}
          className={`p-4 rounded-lg border-2 transition-colors ${
            filterLevel === 'high' ? 'border-red-500 bg-red-50' : 'border-gray-200 hover:border-gray-300'
          }`}
        >
          <div className="text-2xl font-bold text-red-600">{byLevel.high}</div>
          <div className="text-sm text-gray-600">High Priority</div>
        </button>
        <button
          onClick={() => setFilterLevel('medium')}
          className={`p-4 rounded-lg border-2 transition-colors ${
            filterLevel === 'medium' ? 'border-yellow-500 bg-yellow-50' : 'border-gray-200 hover:border-gray-300'
          }`}
        >
          <div className="text-2xl font-bold text-yellow-600">{byLevel.medium}</div>
          <div className="text-sm text-gray-600">Medium Priority</div>
        </button>
        <button
          onClick={() => setFilterLevel('low')}
          className={`p-4 rounded-lg border-2 transition-colors ${
            filterLevel === 'low' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
          }`}
        >
          <div className="text-2xl font-bold text-blue-600">{byLevel.low}</div>
          <div className="text-sm text-gray-600">Low Priority</div>
        </button>
      </div>

      {/* Time Range Filter */}
      <div className="mb-6 flex items-center gap-4">
        <span className="text-sm text-gray-600">Time range:</span>
        <div className="flex gap-2">
          {[7, 30, 60, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 rounded-md text-sm ${
                days === d
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {d} days
            </button>
          ))}
        </div>
      </div>

      {/* Signal List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin h-8 w-8 border-4 border-primary-500 border-t-transparent rounded-full"></div>
        </div>
      ) : filteredSignals.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No signals found for the selected filters
        </div>
      ) : (
        <div className="space-y-4">
          {filteredSignals.map((signal, idx) => (
            <div
              key={`${signal.accession_number}-${idx}`}
              className={`p-5 rounded-lg border-2 ${getCombinedColor(signal.combined_signal_level)}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase text-white ${getCombinedBadge(signal.combined_signal_level)}`}>
                      {getCombinedLabel(signal.combined_signal_level)}
                    </span>
                    <Link
                      to={`/company/${signal.cik}`}
                      className="text-lg font-semibold text-gray-900 hover:text-primary-600"
                    >
                      {signal.company_name}
                    </Link>
                    {signal.ticker && (
                      <span className="text-sm text-gray-500">({signal.ticker})</span>
                    )}
                  </div>

                  <Link
                    to={`/event/${encodeURIComponent(signal.accession_number)}`}
                    className="block text-gray-700 font-medium mb-2 hover:text-primary-600"
                  >
                    {signal.signal_summary} &rarr;
                  </Link>

                  <div className="flex flex-wrap gap-2 mb-2">
                    {signal.items.map((item) => (
                      <span
                        key={item}
                        className="px-2 py-1 bg-white/50 rounded text-xs font-mono"
                      >
                        Item {item}
                      </span>
                    ))}
                  </div>

                  {/* Insider Context */}
                  {signal.insider_context && signal.insider_context.trade_count > 0 && (
                    <div className="mt-2 p-2 rounded bg-white/60 border border-amber-200">
                      {/* Person-level matches — most compelling evidence */}
                      {signal.insider_context.person_matches && signal.insider_context.person_matches.length > 0 && (
                        <div className="mb-2 p-2 rounded bg-yellow-50 border border-yellow-300">
                          <div className="text-xs font-semibold text-yellow-900 mb-1">Person in Filing + Insider Trade Match</div>
                          {signal.insider_context.person_matches.map((match, midx) => (
                            <div key={midx} className="text-xs text-yellow-800 font-medium">
                              {match}
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="flex items-center gap-2 text-sm">
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          signal.insider_context.net_direction === 'buying' ? 'bg-green-100 text-green-800' :
                          signal.insider_context.net_direction === 'selling' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {signal.insider_context.net_direction === 'buying' ? 'Insider Buying' :
                           signal.insider_context.net_direction === 'selling' ? 'Insider Selling' :
                           'Insider Activity'}
                        </span>
                        <span className="text-gray-600 text-xs">
                          {signal.insider_context.trade_count} trade{signal.insider_context.trade_count !== 1 ? 's' : ''} within 60 days
                        </span>
                        {signal.insider_context.cluster_activity && (
                          <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                            Cluster
                          </span>
                        )}
                      </div>
                      {signal.insider_context.notable_trades.length > 0 && (
                        <div className="mt-1 text-xs text-amber-800 italic">
                          {signal.insider_context.notable_trades[0]}
                        </div>
                      )}
                    </div>
                  )}

                  {signal.persons_mentioned.length > 0 && (
                    <div className="text-sm text-gray-600 mt-2">
                      <span className="font-medium">Persons mentioned:</span>{' '}
                      {signal.persons_mentioned.slice(0, 3).join(', ')}
                      {signal.persons_mentioned.length > 3 && (
                        <span className="text-gray-400"> +{signal.persons_mentioned.length - 3} more</span>
                      )}
                    </div>
                  )}
                </div>

                <div className="text-right ml-4">
                  <div className="text-sm font-medium text-gray-900">
                    {signal.filing_date}
                  </div>
                  <a
                    href={`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${signal.cik}&type=8-K`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-primary-600 hover:underline"
                  >
                    View Filing
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="mt-8 p-4 bg-gray-50 rounded-lg">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Signal Level Guide</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="inline-block w-3 h-3 rounded bg-purple-600 mr-2"></span>
            <span className="font-medium">CRITICAL:</span>
            <span className="text-gray-600 ml-1">HIGH signal + insider buying confirms deal intent</span>
          </div>
          <div>
            <span className="inline-block w-3 h-3 rounded bg-red-500 mr-2"></span>
            <span className="font-medium">HIGH:</span>
            <span className="text-gray-600 ml-1">Material Agreement + Governance/Exec changes</span>
          </div>
          <div>
            <span className="inline-block w-3 h-3 rounded bg-yellow-500 mr-2"></span>
            <span className="font-medium">MEDIUM:</span>
            <span className="text-gray-600 ml-1">Material Agreement alone, multiple exec changes</span>
          </div>
          <div>
            <span className="inline-block w-3 h-3 rounded bg-blue-500 mr-2"></span>
            <span className="font-medium">LOW:</span>
            <span className="text-gray-600 ml-1">Single executive or governance change</span>
          </div>
        </div>
      </div>
    </div>
  )
}
