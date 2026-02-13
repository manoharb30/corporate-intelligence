import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { profileApi, CompanyProfile as CompanyProfileType } from '../services/api'
import PriceChart, { ChartMarker } from '../components/PriceChart'

type TabKey = 'signals' | 'insider-trades' | 'people' | 'connections' | 'subsidiaries'

export default function CompanyProfile() {
  const { cik } = useParams<{ cik: string }>()
  const [profile, setProfile] = useState<CompanyProfileType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabKey>('signals')
  const [highlightDate, setHighlightDate] = useState<string | null>(null)

  useEffect(() => {
    if (cik) {
      loadProfile(cik)
    }
  }, [cik])

  const loadProfile = async (cik: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await profileApi.getProfile(cik)
      setProfile(response.data)
    } catch {
      setError('Company not found')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin h-8 w-8 border-4 border-primary-500 border-t-transparent rounded-full"></div>
      </div>
    )
  }

  if (error || !profile) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">Company Not Found</h2>
        <p className="mt-2 text-gray-600">{error}</p>
        <Link to="/" className="mt-4 inline-block text-primary-600 hover:underline">Back to Dashboard</Link>
      </div>
    )
  }

  const { basic_info, counts, signals, connections, officers, directors, recent_subsidiaries, insider_trades, insider_trade_summary } = profile

  // Build chart markers from signals + insider trades
  const chartMarkers: ChartMarker[] = []
  signals.forEach(s => {
    chartMarkers.push({
      date: s.filing_date,
      label: s.item_number,
      color: s.signal_type === 'material_agreement' ? '#8b5cf6' : '#3b82f6',
      shape: 'square',
      position: 'aboveBar',
    })
  })
  insider_trades?.forEach(t => {
    if (t.total_value >= 50000) {
      chartMarkers.push({
        date: t.transaction_date,
        label: t.transaction_code === 'P' ? 'B' : 'S',
        color: t.transaction_code === 'P' ? '#10b981' : '#ef4444',
        shape: t.transaction_code === 'P' ? 'arrowUp' : 'arrowDown',
        position: t.transaction_code === 'P' ? 'belowBar' : 'aboveBar',
      })
    }
  })

  const tabs: { key: TabKey; label: string; count: number }[] = [
    { key: 'signals', label: 'Signals', count: signals.length },
    { key: 'insider-trades', label: 'Insider Activity', count: insider_trades?.length || 0 },
    { key: 'people', label: 'Leadership', count: officers.length + directors.length },
    { key: 'connections', label: 'Connections', count: connections.length },
    { key: 'subsidiaries', label: 'Subsidiaries', count: recent_subsidiaries.length },
  ]

  const getTradeColor = (code: string) => {
    switch (code) {
      case 'P': return 'bg-green-100 text-green-800'
      case 'S': return 'bg-red-100 text-red-800'
      case 'A': return 'bg-blue-100 text-blue-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getSignalTypeColor = (signalType: string) => {
    switch (signalType) {
      case 'acquisition_disposition':
      case 'control_change':
        return 'bg-red-100 text-red-800'
      case 'material_agreement':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-blue-100 text-blue-800'
    }
  }

  return (
    <div>
      <Link to="/" className="text-sm text-primary-600 hover:underline inline-block mb-4">&larr; Dashboard</Link>

      {/* Header */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 mb-4">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-gray-900">{basic_info.name}</h1>
              {basic_info.ticker && (
                <span className="px-2.5 py-1 bg-primary-100 text-primary-800 rounded text-sm font-semibold">
                  {basic_info.ticker}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
              <span>CIK: {basic_info.cik}</span>
              {basic_info.sic && <span>SIC: {basic_info.sic}</span>}
              {basic_info.state_of_incorporation && <span>{basic_info.state_of_incorporation}</span>}
            </div>
            {basic_info.sic_description && (
              <p className="text-sm text-gray-600 mt-1">{basic_info.sic_description}</p>
            )}
          </div>
          {/* Stat pills */}
          <div className="flex gap-3">
            <div className="text-center px-3">
              <div className="text-lg font-bold text-gray-900">{counts.officers}</div>
              <div className="text-xs text-gray-500">Officers</div>
            </div>
            <div className="text-center px-3">
              <div className="text-lg font-bold text-gray-900">{counts.directors}</div>
              <div className="text-xs text-gray-500">Directors</div>
            </div>
            <div className="text-center px-3">
              <div className="text-lg font-bold text-gray-900">{counts.board_connections}</div>
              <div className="text-xs text-gray-500">Interlocks</div>
            </div>
            <div className="text-center px-3">
              <div className="text-lg font-bold text-gray-900">{counts.insider_trades}</div>
              <div className="text-xs text-gray-500">Trades</div>
            </div>
          </div>
        </div>
      </div>

      {/* Price Chart */}
      {basic_info.ticker && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 mb-4">
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Price Action</h2>
          <PriceChart
            ticker={basic_info.ticker}
            markers={chartMarkers}
            height={280}
            onMarkerClick={(marker) => {
              // Switch to the right tab and highlight
              if (marker.shape === 'square') {
                setActiveTab('signals')
              } else {
                setActiveTab('insider-trades')
              }
              setHighlightDate(null)
              setTimeout(() => setHighlightDate(marker.date), 0)
            }}
          />
          <div className="flex gap-4 mt-2 text-xs text-gray-500">
            {chartMarkers.some(m => m.shape === 'square') && (
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 bg-purple-500 rounded-sm inline-block"></span> 8-K Filing
              </span>
            )}
            {chartMarkers.some(m => m.color === '#10b981') && (
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 bg-green-500 rounded-sm inline-block"></span> Insider Buy
              </span>
            )}
            {chartMarkers.some(m => m.color === '#ef4444') && (
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 bg-red-500 rounded-sm inline-block"></span> Insider Sell
              </span>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-4">
        <nav className="flex gap-6">
          {tabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
              <span className="ml-1.5 px-1.5 py-0.5 bg-gray-100 rounded-full text-xs">{tab.count}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        {/* Signals */}
        {activeTab === 'signals' && (
          <div className="divide-y divide-gray-100">
            {signals.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No signals recorded</div>
            ) : (
              signals.map((signal, idx) => (
                <Link
                  key={idx}
                  to={`/signal/${encodeURIComponent(signal.accession_number)}`}
                  className={`block p-4 transition-colors ${
                    highlightDate === signal.filing_date
                      ? 'bg-indigo-50 ring-2 ring-indigo-200'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${getSignalTypeColor(signal.signal_type)}`}>
                          Item {signal.item_number}
                        </span>
                        <span className="font-medium text-gray-900">{signal.item_name}</span>
                      </div>
                    </div>
                    <div className="text-sm text-gray-500">{signal.filing_date}</div>
                  </div>
                </Link>
              ))
            )}
          </div>
        )}

        {/* Insider Trades */}
        {activeTab === 'insider-trades' && (
          <div>
            {insider_trade_summary && insider_trade_summary.total > 0 && (
              <div className="p-4 border-b border-gray-100 bg-gray-50">
                <div className="flex items-center gap-4 flex-wrap text-sm">
                  <span><span className="font-medium text-gray-700">Insiders:</span> {insider_trade_summary.unique_insiders}</span>
                  <span><span className="font-medium text-green-700">Buys:</span> {insider_trade_summary.purchases}</span>
                  <span><span className="font-medium text-red-700">Sells:</span> {insider_trade_summary.sales}</span>
                </div>
              </div>
            )}
            <div className="divide-y divide-gray-100">
              {(!insider_trades || insider_trades.length === 0) ? (
                <div className="p-6 text-center text-gray-500">No insider trades recorded</div>
              ) : (
                insider_trades.map((trade, idx) => (
                  <div key={idx} className={`p-4 transition-colors ${
                    highlightDate === trade.transaction_date
                      ? 'bg-indigo-50 ring-2 ring-indigo-200'
                      : 'hover:bg-gray-50'
                  }`}>
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${getTradeColor(trade.transaction_code)}`}>
                            {trade.transaction_type}
                          </span>
                          <span className="font-medium text-gray-900">{trade.insider_name}</span>
                        </div>
                        {trade.insider_title && <div className="text-sm text-gray-500">{trade.insider_title}</div>}
                        <div className="text-sm text-gray-600 mt-1">
                          {trade.shares.toLocaleString()} shares
                          {trade.price_per_share > 0 && <> @ ${trade.price_per_share.toFixed(2)}</>}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm text-gray-500">{trade.transaction_date}</div>
                        {trade.total_value > 0 && (
                          <div className={`text-sm font-medium ${trade.transaction_code === 'P' ? 'text-green-600' : trade.transaction_code === 'S' ? 'text-red-600' : 'text-gray-600'}`}>
                            ${trade.total_value.toLocaleString()}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Leadership */}
        {activeTab === 'people' && (
          <div className="p-6 grid grid-cols-2 gap-8">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Officers</h3>
              {officers.length === 0 ? (
                <p className="text-gray-500 text-sm">No officers recorded</p>
              ) : (
                <ul className="space-y-3">
                  {officers.map((officer, idx) => (
                    <li key={idx} className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center shrink-0">
                        <span className="text-purple-600 text-sm font-medium">{officer.name.charAt(0)}</span>
                      </div>
                      <div>
                        <div className="font-medium text-gray-900 text-sm">{officer.name}</div>
                        {officer.title && <div className="text-xs text-gray-500">{officer.title}</div>}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Directors</h3>
              {directors.length === 0 ? (
                <p className="text-gray-500 text-sm">No directors recorded</p>
              ) : (
                <ul className="space-y-3">
                  {directors.map((director, idx) => (
                    <li key={idx} className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center shrink-0">
                        <span className="text-green-600 text-sm font-medium">{director.name.charAt(0)}</span>
                      </div>
                      <div>
                        <div className="font-medium text-gray-900 text-sm">{director.name}</div>
                        {director.other_boards.length > 0 && (
                          <div className="text-xs text-gray-500">
                            Also on: {director.other_boards.slice(0, 2).join(', ')}
                            {director.other_boards.length > 2 && ` +${director.other_boards.length - 2}`}
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Connections */}
        {activeTab === 'connections' && (
          <div className="divide-y divide-gray-100">
            {connections.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No board connections found</div>
            ) : (
              connections.map((conn, idx) => (
                <div key={idx} className="p-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <Link to={`/company/${conn.cik}`} className="font-medium text-primary-600 hover:underline">
                        {conn.company_name}
                      </Link>
                      <div className="text-sm text-gray-600 mt-0.5">
                        Shared: {conn.shared_directors.join(', ')}
                      </div>
                    </div>
                    <span className="text-sm text-gray-500">
                      {conn.shared_directors.length} director{conn.shared_directors.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Subsidiaries */}
        {activeTab === 'subsidiaries' && (
          <div className="divide-y divide-gray-100">
            {recent_subsidiaries.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No subsidiaries recorded</div>
            ) : (
              recent_subsidiaries.map((sub, idx) => (
                <div key={idx} className="p-4 hover:bg-gray-50 flex items-center justify-between">
                  <span className="font-medium text-gray-900">{sub.name}</span>
                  {sub.jurisdiction && (
                    <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-sm">{sub.jurisdiction}</span>
                  )}
                </div>
              ))
            )}
            {counts.subsidiaries > recent_subsidiaries.length && (
              <div className="p-4 text-center text-sm text-gray-500">
                Showing {recent_subsidiaries.length} of {counts.subsidiaries}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
