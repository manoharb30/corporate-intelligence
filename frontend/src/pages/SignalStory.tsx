import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { eventDetailApi, EventDetailResponse, ClusterBuyerDetail } from '../services/api'
import DecisionCard from '../components/DecisionCard'
import PriceChart, { ChartMarker } from '../components/PriceChart'
import InsiderTimeline from '../components/InsiderTimeline'
import MiniGraph from '../components/MiniGraph'

function formatValue(val: number): string {
  if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`
  if (val >= 1e3) return `$${Math.round(val / 1e3)}K`
  return ''
}

const levelBadge: Record<string, string> = {
  critical: 'bg-purple-600 text-white animate-pulse',
  high_bearish: 'bg-red-700 text-white',
  high: 'bg-red-500 text-white',
  medium: 'bg-yellow-500 text-white',
  low: 'bg-blue-500 text-white',
}

const levelLabel: Record<string, string> = {
  critical: 'CRITICAL',
  high_bearish: 'HIGH BEARISH',
  high: 'HIGH',
  medium: 'MEDIUM',
  low: 'LOW',
}

export default function SignalStory() {
  const { accessionNumber } = useParams<{ accessionNumber: string }>()
  const [data, setData] = useState<EventDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandTerms, setExpandTerms] = useState(false)
  const [expandWatch, setExpandWatch] = useState(false)
  const [expandCompanyContext, setExpandCompanyContext] = useState(false)
  const [highlightDate, setHighlightDate] = useState<string | null>(null)

  useEffect(() => {
    if (accessionNumber) {
      setLoading(true)
      setError(null)
      eventDetailApi.getDetail(accessionNumber)
        .then(res => setData(res.data))
        .catch(err => setError(err instanceof Error ? err.message : 'Failed to load'))
        .finally(() => setLoading(false))
    }
  }, [accessionNumber])

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full mb-4"></div>
        <p className="text-gray-600">Analyzing signal...</p>
        <p className="text-sm text-gray-400 mt-1">First-time analysis may take a moment</p>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Signal Not Found</h2>
        <p className="text-gray-600 mb-4">{error || 'Could not load signal details.'}</p>
        <Link to="/signals" className="text-primary-600 hover:underline">Back to Signals</Link>
      </div>
    )
  }

  const { event, analysis, timeline, deals, company } = data
  const combinedLevel = data.combined_signal_level || event.signal_level
  const insiderCtx = data.insider_context
  const isCluster = data.signal_type === 'insider_cluster'

  // Build chart markers from timeline
  const chartMarkers: ChartMarker[] = []
  if (event.filing_date) {
    chartMarkers.push({
      date: event.filing_date,
      label: 'Filing',
      color: '#8b5cf6',
      shape: 'square',
      position: 'aboveBar',
    })
  }
  timeline.forEach(entry => {
    if (entry.type === 'event' && !entry.is_current && entry.date) {
      chartMarkers.push({
        date: entry.date,
        label: entry.signal_level === 'high' ? 'H' : entry.signal_level === 'medium' ? 'M' : 'E',
        color: '#3b82f6',
        shape: 'square',
        position: 'aboveBar',
      })
    }
    if (entry.type === 'trade' && entry.date && entry.notable) {
      const isBullish = entry.trade_type === 'buy' || entry.trade_type === 'exercise_hold'
      const isBearish = entry.trade_type === 'sell' || entry.trade_type === 'disposition'
      chartMarkers.push({
        date: entry.date,
        label: isBullish ? 'B' : isBearish ? 'S' : 'T',
        color: isBullish ? '#10b981' : isBearish ? '#ef4444' : '#f59e0b',
        shape: isBullish ? 'arrowUp' : isBearish ? 'arrowDown' : 'circle',
        position: isBullish ? 'belowBar' : 'aboveBar',
      })
    }
  })

  // Insider summary stats
  const tradeEntries = timeline.filter(e => e.type === 'trade')
  const buyTrades = tradeEntries.filter(e => e.trade_type === 'buy' || e.trade_type === 'exercise_hold')
  const sellTrades = tradeEntries.filter(e => e.trade_type === 'sell')
  const exerciseSellTrades = tradeEntries.filter(e => e.trade_type === 'exercise_sell')

  // SEC EDGAR link (not applicable for cluster signals)
  const edgarUrl = accessionNumber && !isCluster
    ? `https://www.sec.gov/Archives/edgar/data/${company.cik}/${accessionNumber.replace(/-/g, '')}/${accessionNumber}-index.htm`
    : null

  return (
    <div className="max-w-5xl mx-auto">
      {/* Back link */}
      <Link to="/signals" className="text-sm text-primary-600 hover:underline inline-block mb-4">
        &larr; Back to Signals
      </Link>

      {/* ===== Decision Card ===== */}
      {data.decision_card && <DecisionCard card={data.decision_card} />}

      {/* ===== Chapter 1: The Filing ===== */}
      <section className="mb-8">
        <div className="flex items-start gap-3 mb-3">
          <span className={`px-3 py-1 rounded text-sm font-bold uppercase shrink-0 ${levelBadge[combinedLevel] || levelBadge.low}`}>
            {levelLabel[combinedLevel] || combinedLevel}
          </span>
          <div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setExpandCompanyContext(!expandCompanyContext)}
                className="text-2xl font-bold text-gray-900 hover:text-primary-600 text-left"
                title="About this company"
              >
                {company.name}
              </button>
              {company.ticker && <span className="text-lg text-gray-500">({company.ticker})</span>}
            </div>
            <div className="flex items-center gap-3 mt-1 text-sm text-gray-600">
              <span>{isCluster ? `Cluster detected: ${event.filing_date}` : `Filed: ${event.filing_date}`}</span>
              <span className="text-gray-300">|</span>
              <span>{event.signal_summary}</span>
            </div>
          </div>
        </div>

        {/* Company Context (expandable via company name click) */}
        {expandCompanyContext && (
          <div className="mb-4 bg-white rounded-lg border border-gray-200 shadow-sm p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-800">About {company.name}</h3>
              <button onClick={() => setExpandCompanyContext(false)} className="text-gray-400 hover:text-gray-600 text-sm">Close</button>
            </div>

            {data.company_context ? (
              <>
                {/* Industry & State */}
                <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                  {data.company_context.sic_description && (
                    <div><span className="font-medium text-gray-800">Industry:</span> {data.company_context.sic_description}</div>
                  )}
                  {data.company_context.state_of_incorporation && (
                    <div><span className="font-medium text-gray-800">Incorporated:</span> {data.company_context.state_of_incorporation}</div>
                  )}
                  {data.company_context.subsidiaries_count > 0 && (
                    <div><span className="font-medium text-gray-800">Subsidiaries:</span> {data.company_context.subsidiaries_count}</div>
                  )}
                </div>

                {/* Officers */}
                {data.company_context.officers.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Officers</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
                      {data.company_context.officers.map((officer, idx) => (
                        <div key={idx} className="text-sm text-gray-700">
                          <span className="font-medium">{officer.name}</span>
                          {officer.title && <span className="text-gray-500 ml-1">- {officer.title}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Directors */}
                {data.company_context.directors.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Directors</h4>
                    <div className="space-y-1">
                      {data.company_context.directors.map((director, idx) => (
                        <div key={idx} className="text-sm text-gray-700">
                          <span className="font-medium">{director.name}</span>
                          {director.other_boards.length > 0 && (
                            <span className="text-xs text-purple-600 ml-2">
                              Also on: {director.other_boards.join(', ')}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Board Connections */}
                {data.company_context.board_connections.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Board Connections</h4>
                    <div className="space-y-1.5">
                      {data.company_context.board_connections.map((conn, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-sm">
                          <Link to={`/signals?cik=${conn.cik}`} className="font-medium text-primary-600 hover:underline">
                            {conn.company_name}
                          </Link>
                          <span className="text-xs text-gray-500">
                            via {conn.shared_directors.join(', ')}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {data.company_context.officers.length === 0 && data.company_context.directors.length === 0 && (
                  <p className="text-xs text-gray-400">Officer and director data not yet available for this company.</p>
                )}
              </>
            ) : (
              <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                {company.ticker && <div><span className="font-medium text-gray-800">Ticker:</span> {company.ticker}</div>}
                <div><span className="font-medium text-gray-800">CIK:</span> {company.cik}</div>
                <p className="text-xs text-gray-400 w-full mt-1">Restart backend to load full company details.</p>
              </div>
            )}

            {/* View all signals link */}
            <Link
              to={`/signals?cik=${company.cik}`}
              className="inline-block text-sm text-primary-600 hover:underline font-medium"
            >
              View all signals for {company.name} &rarr;
            </Link>
          </div>
        )}

        {!isCluster && (
          <div className="flex flex-wrap gap-2 mb-4">
            {event.items.map((item) => (
              <span key={item.item_number} className="px-2.5 py-1 bg-gray-100 border border-gray-200 rounded text-xs font-mono">
                Item {item.item_number}: {item.item_name}
              </span>
            ))}
          </div>
        )}

        {isCluster && data.cluster_detail ? (
          /* ===== Cluster Chapter: The Insider Cluster ===== */
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-gray-900">The Insider Cluster</h2>
              <span className="px-3 py-1 bg-emerald-100 text-emerald-800 rounded-full text-sm font-medium">
                {data.cluster_detail.num_buyers} Insiders Buying
              </span>
            </div>

            <p className="text-gray-700 leading-relaxed mb-4">{analysis.summary}</p>

            {/* Buyer Cards */}
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">Buyers</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {data.cluster_detail.buyers.map((buyer: ClusterBuyerDetail, idx: number) => (
                  <div key={idx} className="flex items-start gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                    <div className="shrink-0 w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center text-sm font-bold">
                      {buyer.name.charAt(0)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-gray-900 text-sm">{buyer.name}</p>
                      {buyer.title && <p className="text-xs text-gray-500">{buyer.title}</p>}
                      <div className="flex items-center gap-3 mt-1 text-xs">
                        <span className="text-emerald-700 font-medium">${buyer.total_value.toLocaleString()}</span>
                        <span className="text-gray-400">{buyer.trade_count} trade{buyer.trade_count !== 1 ? 's' : ''}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Window info */}
            <p className="text-xs text-gray-500">
              Cluster window: {data.cluster_detail.window_start} to {data.cluster_detail.window_end}
            </p>

            {/* What to Watch */}
            {analysis.forward_looking && analysis.forward_looking !== 'N/A' && (
              <div className="mt-4">
                <button
                  onClick={() => setExpandWatch(!expandWatch)}
                  className="text-sm font-semibold text-gray-600 uppercase tracking-wide hover:text-primary-600 flex items-center gap-1"
                >
                  What to Watch
                  <span className="text-xs">{expandWatch ? '\u25B2' : '\u25BC'}</span>
                </button>
                {expandWatch && (
                  <p className="mt-2 text-sm text-gray-700 bg-amber-50 border border-amber-200 rounded p-3">
                    {analysis.forward_looking}
                  </p>
                )}
              </div>
            )}
          </div>
        ) : (
          /* ===== Filing Chapter: The Filing ===== */
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-gray-900">The Filing</h2>
              <span className="px-3 py-1 bg-indigo-100 text-indigo-800 rounded-full text-sm font-medium">
                {analysis.agreement_type}
              </span>
            </div>

            <p className="text-gray-700 leading-relaxed mb-4">{analysis.summary}</p>

            {/* Parties */}
            {analysis.parties_involved.length > 0 && (
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">Parties Involved</h3>
                <div className="flex flex-wrap gap-2">
                  {analysis.parties_involved.map((party, idx) => (
                    <span key={idx} className="px-3 py-1.5 bg-gray-100 rounded-lg text-sm text-gray-800 font-medium" title={party.source_quote}>
                      {party.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Key Terms (expandable) */}
            {analysis.key_terms.length > 0 && (
              <div className="mb-4">
                <button
                  onClick={() => setExpandTerms(!expandTerms)}
                  className="text-sm font-semibold text-gray-600 uppercase tracking-wide hover:text-primary-600 flex items-center gap-1"
                >
                  Key Terms
                  <span className="text-xs">{expandTerms ? '\u25B2' : '\u25BC'}</span>
                </button>
                {expandTerms && (
                  <div className="mt-2 space-y-2">
                    {analysis.key_terms.map((item, idx) => (
                      <div key={idx} className="border-l-2 border-gray-200 pl-3">
                        <p className="text-sm text-gray-800 font-medium">{item.term}</p>
                        {item.source_quote && (
                          <p className="text-xs text-gray-400 italic mt-0.5">"{item.source_quote}"</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* What to Watch (expandable) */}
            {analysis.forward_looking && analysis.forward_looking !== 'N/A' && (
              <div className="mb-4">
                <button
                  onClick={() => setExpandWatch(!expandWatch)}
                  className="text-sm font-semibold text-gray-600 uppercase tracking-wide hover:text-primary-600 flex items-center gap-1"
                >
                  What to Watch
                  <span className="text-xs">{expandWatch ? '\u25B2' : '\u25BC'}</span>
                </button>
                {expandWatch && (
                  <p className="mt-2 text-sm text-gray-700 bg-amber-50 border border-amber-200 rounded p-3">
                    {analysis.forward_looking}
                  </p>
                )}
              </div>
            )}

            {/* SEC link */}
            {edgarUrl && (
              <a
                href={edgarUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary-600 hover:underline"
              >
                View on SEC EDGAR &rarr;
              </a>
            )}
          </div>
        )}
      </section>

      {/* ===== Chapter 2: The Insider Evidence ===== */}
      <section className="mb-8">
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">The Insider Evidence</h2>

          {tradeEntries.length > 0 ? (
            <>
              <p className="text-sm text-gray-600 mb-4">
                {tradeEntries.length} trade{tradeEntries.length !== 1 ? 's' : ''} in timeline.
                {buyTrades.length > 0 && ` ${buyTrades.length} buy${buyTrades.length !== 1 ? 's' : ''}.`}
                {sellTrades.length > 0 && ` ${sellTrades.length} sell${sellTrades.length !== 1 ? 's' : ''}.`}
                {exerciseSellTrades.length > 0 && ` ${exerciseSellTrades.length} cashless exercise${exerciseSellTrades.length !== 1 ? 's' : ''}.`}
                {insiderCtx && (
                  <> Net: <span className={`font-semibold ${
                    insiderCtx.net_direction === 'buying' ? 'text-green-700' :
                    insiderCtx.net_direction === 'selling' ? 'text-red-700' : 'text-gray-700'
                  }`}>
                    {insiderCtx.net_direction.toUpperCase()}
                    {insiderCtx.net_direction === 'buying' && insiderCtx.total_buy_value > 0 &&
                      formatValue(insiderCtx.total_buy_value) && ` (${formatValue(insiderCtx.total_buy_value)})`}
                    {insiderCtx.net_direction === 'selling' && insiderCtx.total_sell_value > 0 &&
                      formatValue(insiderCtx.total_sell_value) && ` (${formatValue(insiderCtx.total_sell_value)})`}
                  </span></>
                )}
              </p>

              {/* Person matches */}
              {insiderCtx?.person_matches && insiderCtx.person_matches.length > 0 && (
                <div className="mb-4 space-y-1">
                  {insiderCtx.person_matches.map((match, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-sm bg-amber-50 border border-amber-200 rounded px-3 py-2">
                      <span className="text-amber-600 font-bold">!</span>
                      <span className="text-amber-900">{match}</span>
                    </div>
                  ))}
                </div>
              )}

              <InsiderTimeline entries={timeline} maxItems={30} highlightDate={highlightDate} />
            </>
          ) : (
            <p className="text-sm text-gray-500 mt-2">No insider trading data available for this company.</p>
          )}
        </div>
      </section>

      {/* ===== Chapter 3: The Price Action ===== */}
      {company.ticker && (
        <section className="mb-8">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">The Price Action</h2>
            <PriceChart
              ticker={company.ticker}
              markers={chartMarkers}
              height={350}
              onMarkerClick={(marker) => {
                setHighlightDate(null)
                setTimeout(() => setHighlightDate(marker.date), 0)
              }}
            />
            <div className="flex gap-4 mt-3 text-xs text-gray-500">
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 bg-purple-500 rounded-sm inline-block"></span> This Filing
              </span>
              {chartMarkers.some(m => m.color === '#10b981') && (
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-green-500 rounded-sm inline-block"></span> Insider Buy
                </span>
              )}
              {chartMarkers.some(m => m.color === '#ef4444') && (
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-red-500 rounded-sm inline-block"></span> Insider Sell
                </span>
              )}
              {chartMarkers.some(m => m.color === '#3b82f6') && (
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-blue-500 rounded-sm inline-block"></span> Other 8-K Filing
                </span>
              )}
            </div>
          </div>
        </section>
      )}

      {/* ===== Chapter 4: The Network ===== */}
      {(deals.length > 0) && (
        <section className="mb-8">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">The Network</h2>

            {/* Deal connections */}
            <div className="space-y-3 mb-4">
              {deals.map((deal, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3 bg-purple-50 border border-purple-200 rounded-lg">
                  <div className="shrink-0 w-8 h-8 rounded-full bg-purple-500 text-white flex items-center justify-center text-sm font-bold">
                    {deal.name.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Link to={`/signals?cik=${deal.cik}`} className="font-semibold text-gray-900 hover:text-primary-600">
                        {deal.name}
                      </Link>
                      {deal.ticker && <span className="text-sm text-gray-500">({deal.ticker})</span>}
                      <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-medium">
                        {deal.agreement_type}
                      </span>
                    </div>
                    {deal.source_quote && (
                      <p className="text-xs text-gray-500 italic mt-1">"{deal.source_quote}"</p>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Mini graph */}
            <MiniGraph entityId={company.cik} height={300} depth={1} />
          </div>
        </section>
      )}

    </div>
  )
}
