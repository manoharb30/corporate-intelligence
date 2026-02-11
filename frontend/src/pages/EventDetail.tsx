import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { eventDetailApi, EventDetailResponse } from '../services/api'

export default function EventDetail() {
  const { accessionNumber } = useParams<{ accessionNumber: string }>()
  const [data, setData] = useState<EventDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (accessionNumber) {
      loadEventDetail(accessionNumber)
    }
  }, [accessionNumber])

  const loadEventDetail = async (accNum: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await eventDetailApi.getDetail(accNum)
      setData(response.data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load event detail'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const getLevelBadge = (level: string) => {
    switch (level) {
      case 'high':
        return 'bg-red-500 text-white'
      case 'medium':
        return 'bg-yellow-500 text-white'
      default:
        return 'bg-blue-500 text-white'
    }
  }

  const getTradeColor = (tradeType?: string) => {
    switch (tradeType) {
      case 'buy':
        return 'text-green-700 bg-green-50 border-green-200'
      case 'sell':
        return 'text-red-700 bg-red-50 border-red-200'
      default:
        return 'text-gray-700 bg-gray-50 border-gray-200'
    }
  }

  const getTradeIcon = (tradeType?: string) => {
    switch (tradeType) {
      case 'buy':
        return '\u2191'  // up arrow
      case 'sell':
        return '\u2193'  // down arrow
      default:
        return '\u2022'  // bullet
    }
  }

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
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Event Not Found</h2>
        <p className="text-gray-600 mb-4">{error || 'Could not load event details.'}</p>
        <Link to="/" className="text-primary-600 hover:underline">Back to Feed</Link>
      </div>
    )
  }

  const { event, analysis, timeline, deals, company } = data

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link to="/" className="text-sm text-primary-600 hover:underline">&larr; Back to Feed</Link>

        <div className="flex items-center gap-3 mt-3">
          <span className={`px-2.5 py-1 rounded text-xs font-semibold uppercase ${getLevelBadge(event.signal_level)}`}>
            {event.signal_level}
          </span>
          <Link
            to={`/company/${company.cik}`}
            className="text-2xl font-bold text-gray-900 hover:text-primary-600"
          >
            {company.name}
          </Link>
          {company.ticker && (
            <span className="text-lg text-gray-500">({company.ticker})</span>
          )}
        </div>

        <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
          <span>Filed: {event.filing_date}</span>
          <span className="text-gray-300">|</span>
          <span>{event.signal_summary}</span>
        </div>

        <div className="flex flex-wrap gap-2 mt-3">
          {event.items.map((item) => (
            <span
              key={item.item_number}
              className="px-2.5 py-1 bg-gray-100 border border-gray-200 rounded text-xs font-mono"
            >
              Item {item.item_number}: {item.item_name}
            </span>
          ))}
        </div>
      </div>

      {/* Analysis Card */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Analysis</h2>
          <span className="px-3 py-1 bg-indigo-100 text-indigo-800 rounded-full text-sm font-medium">
            {analysis.agreement_type}
          </span>
        </div>

        {/* Summary */}
        <p className="text-gray-700 mb-4 leading-relaxed">{analysis.summary}</p>

        {/* Parties Involved */}
        {analysis.parties_involved.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
              Parties Involved
            </h3>
            <div className="space-y-2">
              {analysis.parties_involved.map((party, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <span className="px-2.5 py-1 bg-gray-100 rounded text-sm text-gray-800 font-medium shrink-0">
                    {party.name}
                  </span>
                  {party.source_quote && (
                    <span className="text-xs text-gray-400 italic leading-5 truncate" title={party.source_quote}>
                      "{party.source_quote}"
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Key Terms */}
        {analysis.key_terms.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
              Key Terms
            </h3>
            <div className="space-y-2">
              {analysis.key_terms.map((item, idx) => (
                <div key={idx} className="border-l-2 border-gray-200 pl-3">
                  <p className="text-sm text-gray-800 font-medium">{item.term}</p>
                  {item.source_quote && (
                    <p className="text-xs text-gray-400 italic mt-0.5">"{item.source_quote}"</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* What to Watch */}
        {analysis.forward_looking && analysis.forward_looking !== 'N/A' && analysis.forward_looking !== 'No forward-looking statements in filing.' && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
              What to Watch
            </h3>
            <p className="text-sm text-gray-700 bg-amber-50 border border-amber-200 rounded p-3">
              {analysis.forward_looking}
            </p>
            {analysis.forward_looking_source && (
              <p className="text-xs text-gray-400 italic mt-1 pl-1">Source: "{analysis.forward_looking_source}"</p>
            )}
          </div>
        )}

        {/* Market Implications */}
        {analysis.market_implications && analysis.market_implications !== 'N/A' && (
          <div>
            <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
              Market Context
            </h3>
            <p className="text-sm text-gray-700">{analysis.market_implications}</p>
            {analysis.market_implications_source && (
              <p className="text-xs text-gray-400 italic mt-1">Source: "{analysis.market_implications_source}"</p>
            )}
          </div>
        )}
      </div>

      {/* Deal Connections */}
      {deals && deals.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Connected Parties
          </h2>
          <div className="space-y-3">
            {deals.map((deal, idx) => (
              <div key={idx} className="flex items-start gap-4 p-3 bg-purple-50 border border-purple-200 rounded-lg">
                <div className="shrink-0 w-8 h-8 rounded-full bg-purple-500 text-white flex items-center justify-center text-sm font-bold">
                  {deal.name.charAt(0)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/company/${deal.cik}`}
                      className="font-semibold text-gray-900 hover:text-primary-600"
                    >
                      {deal.name}
                    </Link>
                    {deal.ticker && (
                      <span className="text-sm text-gray-500">({deal.ticker})</span>
                    )}
                    <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-medium">
                      {deal.agreement_type}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mt-0.5">
                    Filing date: {deal.filing_date}
                    {deal.accession_number && (
                      <>
                        {' '}&middot;{' '}
                        <Link
                          to={`/event/${encodeURIComponent(deal.accession_number)}`}
                          className="text-primary-600 hover:underline"
                        >
                          View filing
                        </Link>
                      </>
                    )}
                  </p>
                  {deal.source_quote && (
                    <p className="text-xs text-gray-400 italic mt-1">
                      "{deal.source_quote}"
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Company Timeline
        </h2>

        {timeline.length === 0 ? (
          <p className="text-gray-500 text-sm">No timeline data available.</p>
        ) : (
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200"></div>

            <div className="space-y-4">
              {timeline.map((entry, idx) => (
                <div
                  key={idx}
                  className={`relative pl-10 ${
                    entry.is_current
                      ? 'bg-primary-50 -mx-6 px-16 py-3 rounded-lg border-2 border-primary-300'
                      : entry.notable
                        ? 'bg-amber-50 -mx-6 px-16 py-2 rounded-lg border border-amber-300'
                        : ''
                  }`}
                >
                  {/* Dot — notable trades get a larger pulsing dot */}
                  <div className={`absolute w-3 h-3 rounded-full border-2 ${
                    entry.is_current
                      ? 'left-2.5 bg-primary-500 border-primary-500'
                      : entry.notable
                        ? 'left-2 w-4 h-4 bg-amber-500 border-amber-500 ring-2 ring-amber-200'
                        : entry.type === 'trade'
                          ? entry.trade_type === 'buy'
                            ? 'left-2.5 bg-green-400 border-green-400'
                            : entry.trade_type === 'sell'
                              ? 'left-2.5 bg-red-400 border-red-400'
                              : 'left-2.5 bg-gray-300 border-gray-300'
                          : 'left-2.5 bg-gray-300 border-gray-300'
                  }`}></div>

                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        <span className="text-xs font-mono text-gray-500">{entry.date}</span>
                        {entry.type === 'event' && entry.signal_level && (
                          <span className={`px-1.5 py-0.5 rounded text-xs font-semibold uppercase text-white ${
                            entry.signal_level === 'high' ? 'bg-red-500' :
                            entry.signal_level === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                          }`}>
                            {entry.signal_level}
                          </span>
                        )}
                        {entry.type === 'trade' && (
                          <span className={`px-1.5 py-0.5 rounded text-xs font-medium border ${getTradeColor(entry.trade_type)}`}>
                            {getTradeIcon(entry.trade_type)} {entry.trade_type === 'buy' ? 'Buy' : entry.trade_type === 'sell' ? 'Sell' : 'Trade'}
                          </span>
                        )}
                        {entry.is_current && (
                          <span className="px-1.5 py-0.5 bg-primary-100 text-primary-700 rounded text-xs font-medium">
                            Current
                          </span>
                        )}
                        {entry.notable && entry.notable_reasons?.map((reason, i) => (
                          <span key={i} className="px-1.5 py-0.5 bg-amber-100 text-amber-800 border border-amber-300 rounded text-xs font-semibold">
                            {reason}
                          </span>
                        ))}
                      </div>
                      <p className={`text-sm font-medium ${entry.notable ? 'text-amber-900' : 'text-gray-900'}`}>
                        {entry.type === 'event' && entry.accession_number && !entry.is_current ? (
                          <Link
                            to={`/event/${encodeURIComponent(entry.accession_number)}`}
                            className="hover:text-primary-600"
                          >
                            {entry.description}
                          </Link>
                        ) : (
                          entry.description
                        )}
                      </p>
                      <p className="text-xs text-gray-500 truncate">{entry.detail}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
