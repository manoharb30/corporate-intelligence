import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { eventDetailApi, EventDetailResponse } from '../services/api'
import PriceChart, { ChartMarker } from '../components/PriceChart'
import InsiderTimeline from '../components/InsiderTimeline'
import VerdictCard from '../components/VerdictCard'
import MiniGraph from '../components/MiniGraph'

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
        <p className="text-gray-600">Analyzing filing...</p>
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
      chartMarkers.push({
        date: entry.date,
        label: entry.trade_type === 'buy' ? 'B' : 'S',
        color: entry.trade_type === 'buy' ? '#10b981' : '#ef4444',
        shape: entry.trade_type === 'buy' ? 'arrowUp' : 'arrowDown',
        position: entry.trade_type === 'buy' ? 'belowBar' : 'aboveBar',
      })
    }
  })

  // Insider summary stats
  const tradeEntries = timeline.filter(e => e.type === 'trade')
  const buyTrades = tradeEntries.filter(e => e.trade_type === 'buy')
  const sellTrades = tradeEntries.filter(e => e.trade_type === 'sell')

  // SEC EDGAR link
  const edgarUrl = accessionNumber
    ? `https://www.sec.gov/Archives/edgar/data/${company.cik}/${accessionNumber.replace(/-/g, '')}/${accessionNumber}-index.htm`
    : null

  return (
    <div className="max-w-5xl mx-auto">
      {/* Back link */}
      <Link to="/signals" className="text-sm text-primary-600 hover:underline inline-block mb-4">
        &larr; Back to Signals
      </Link>

      {/* ===== Chapter 1: The Filing ===== */}
      <section className="mb-8">
        <div className="flex items-start gap-3 mb-3">
          <span className={`px-3 py-1 rounded text-sm font-bold uppercase shrink-0 ${levelBadge[combinedLevel] || levelBadge.low}`}>
            {levelLabel[combinedLevel] || combinedLevel}
          </span>
          <div>
            <div className="flex items-center gap-2">
              <Link to={`/company/${company.cik}`} className="text-2xl font-bold text-gray-900 hover:text-primary-600">
                {company.name}
              </Link>
              {company.ticker && <span className="text-lg text-gray-500">({company.ticker})</span>}
            </div>
            <div className="flex items-center gap-3 mt-1 text-sm text-gray-600">
              <span>Filed: {event.filing_date}</span>
              <span className="text-gray-300">|</span>
              <span>{event.signal_summary}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mb-4">
          {event.items.map((item) => (
            <span key={item.item_number} className="px-2.5 py-1 bg-gray-100 border border-gray-200 rounded text-xs font-mono">
              Item {item.item_number}: {item.item_name}
            </span>
          ))}
        </div>

        {/* Analysis Card */}
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
                {insiderCtx && (
                  <> Net: <span className={`font-semibold ${
                    insiderCtx.net_direction === 'buying' ? 'text-green-700' :
                    insiderCtx.net_direction === 'selling' ? 'text-red-700' : 'text-gray-700'
                  }`}>
                    {insiderCtx.net_direction.toUpperCase()}
                    {insiderCtx.net_direction === 'buying' && insiderCtx.total_buy_value > 0 &&
                      ` ($${(insiderCtx.total_buy_value / 1e6).toFixed(1)}M)`}
                    {insiderCtx.net_direction === 'selling' && insiderCtx.total_sell_value > 0 &&
                      ` ($${(insiderCtx.total_sell_value / 1e6).toFixed(1)}M)`}
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
                      <Link to={`/company/${deal.cik}`} className="font-semibold text-gray-900 hover:text-primary-600">
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

      {/* ===== Chapter 5: The Verdict ===== */}
      <section className="mb-8">
        <VerdictCard
          signalLevel={event.signal_level}
          combinedSignalLevel={combinedLevel}
          signalSummary={event.signal_summary}
          insiderContext={insiderCtx}
          itemNumbers={event.item_numbers}
          companyName={company.name}
        />
      </section>
    </div>
  )
}
