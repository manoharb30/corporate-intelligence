import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { eventDetailApi, signalPerfApi, EventDetailResponse, ClusterBuyerDetail, SignalPerf } from '../services/api'

function formatValue(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`
  return `$${value.toLocaleString()}`
}

export default function SignalDetail() {
  const { accessionNumber } = useParams<{ accessionNumber: string }>()
  const [data, setData] = useState<EventDetailResponse | null>(null)
  const [perf, setPerf] = useState<SignalPerf | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!accessionNumber) return
    let ignore = false
    setLoading(true)
    setError(null)

    // Fetch signal detail + performance data in parallel
    const detailPromise = eventDetailApi.getDetail(accessionNumber)
    const perfPromise = signalPerfApi.getAll('buy', false, false, 1000)

    Promise.all([detailPromise, perfPromise])
      .then(([detailRes, perfRes]) => {
        if (ignore) return
        setData(detailRes.data)
        // Find matching SignalPerformance by signal_id (accession number)
        const match = (perfRes.data || []).find(
          (s: SignalPerf) => s.signal_id === accessionNumber
        )
        if (match) setPerf(match)
      })
      .catch((err) => {
        if (!ignore) setError(err.response?.status === 404 ? 'Signal not found' : 'Failed to load signal')
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })

    return () => { ignore = true }
  }, [accessionNumber])

  if (loading) return <div className="text-center py-20 text-gray-500">Loading...</div>
  if (error) return <div className="text-center py-20 text-gray-500">{error}</div>
  if (!data) return null

  const company = data.company
  const cluster = data.cluster_detail
  const buyers: ClusterBuyerDetail[] = cluster?.buyers || []
  const totalValue = buyers.reduce((sum, b) => sum + b.total_value, 0)
  const numInsiders = cluster?.num_buyers || buyers.length

  // Conviction level — read directly from backend signal_level.
  // Backend definition: 'high' = 3+ distinct buyers; 'medium' = 2 buyers (minimum strong_buy).
  // Previously this was a frontend heuristic (≤5 buyers AND <$1M) that mislabeled medium as high.
  const isHighConviction = data.event.signal_level === 'high'

  // Local color hints for the per-attribute HR breakdown below (NOT used for conviction label).
  const isSmallCluster = numInsiders <= 5
  const isModestValue = totalValue < 1_000_000

  // Market cap bucket HR (from FINAL-NUMBERS.md)
  const mcapHR = perf?.market_cap
    ? perf.market_cap < 1e9 ? '71%' : perf.market_cap < 3e9 ? '64%' : '65%'
    : null
  const mcapLabel = perf?.market_cap
    ? perf.market_cap < 1e9 ? '$300M–$1B' : perf.market_cap < 3e9 ? '$1B–$3B' : '$3B–$5B'
    : null

  // Insider count HR
  const insiderHR = numInsiders === 2 ? '62%' : numInsiders === 3 ? '68%' : numInsiders === 4 ? '74%' : numInsiders === 5 ? '100%' : '23%'

  // Value bucket HR
  const valueHR = totalValue < 200_000 ? '74%' : totalValue < 500_000 ? '61%' : totalValue < 1_000_000 ? '64%' : '58%'

  return (
    <div>
      {/* Back link */}
      <Link to="/" className="text-gray-600 text-sm hover:text-gray-900 mb-4 inline-block">
        ← Back to signals
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-start mb-6">
        <div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="font-extrabold text-3xl tracking-tight">{company.ticker || '—'}</span>
            <span className="text-gray-500 text-lg">{company.name}</span>
          </div>
          <div className="mt-2 text-sm text-gray-500">
            Signal date: {data.event.filing_date}
          </div>
        </div>
        {isHighConviction ? (
          <span className="self-start bg-green-50 text-green-800 border border-green-200 px-3 py-1 rounded-md text-sm font-bold uppercase">
            High Conviction
          </span>
        ) : (
          <span className="self-start bg-slate-100 text-slate-700 border border-slate-200 px-3 py-1 rounded-md text-sm font-bold uppercase">
            Medium Conviction
          </span>
        )}
      </div>

      {/* Signal profile */}
      <div className={`rounded-lg p-4 mb-6 ${isHighConviction ? 'bg-green-50 border border-green-200' : 'bg-gray-50 border border-gray-200'}`}>
        <div className="text-sm font-semibold mb-2">
          Signal Profile
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-2 text-sm">
          <div>
            <span className="text-gray-500">Insiders: </span>
            <span className="font-semibold">{numInsiders}</span>
            <span className={`ml-1 ${isSmallCluster ? 'text-green-700' : 'text-amber-700'}`}>
              ({insiderHR} HR)
            </span>
            {numInsiders >= 6 && <span className="text-amber-700 ml-1">⚠</span>}
          </div>
          <div>
            <span className="text-gray-500">Value: </span>
            <span className="font-semibold">{formatValue(totalValue)}</span>
            <span className={`ml-1 ${isModestValue ? 'text-green-700' : 'text-amber-700'}`}>
              ({valueHR} HR)
            </span>
          </div>
          {mcapLabel && (
            <div>
              <span className="text-gray-500">Market cap: </span>
              <span className="font-semibold">{mcapLabel}</span>
              <span className="text-green-700 ml-1">({mcapHR} HR)</span>
            </div>
          )}
        </div>
        <div className="text-xs text-gray-500 mt-2">
          {isHighConviction
            ? 'High conviction (3+ distinct buyers) historically: 68.4% hit rate, +9.5% alpha vs SPY (79 mature signals).'
            : 'Medium conviction (2 buyers, the minimum strong_buy threshold) historically: 65.1% hit rate, +7.8% alpha vs SPY (63 mature signals).'}
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3 md:flex md:gap-10 mb-6 pb-6 border-b border-gray-200">
        <div>
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Total Value</div>
          <div className="text-2xl font-extrabold tracking-tight">{formatValue(totalValue)}</div>
        </div>
        <div>
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Insiders</div>
          <div className="text-2xl font-extrabold tracking-tight">{numInsiders}</div>
        </div>
        {perf && (
          <>
            <div>
              <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Entry Price</div>
              <div className="text-2xl font-extrabold tracking-tight">
                {perf.price_day0 ? `$${perf.price_day0.toFixed(2)}` : '—'}
              </div>
            </div>
            {perf.is_mature && perf.return_day0 != null && (
              <div>
                <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">90-Day Return</div>
                <div className={`text-2xl font-extrabold tracking-tight ${
                  perf.return_day0 >= 0 ? 'text-green-700' : 'text-red-800'
                }`}>
                  {perf.return_day0 >= 0 ? '↑ ' : '↓ '}{Math.abs(perf.return_day0).toFixed(1)}%
                  <span className="text-sm font-normal text-gray-500 ml-1">
                    (${perf.price_day90?.toFixed(2)})
                  </span>
                </div>
              </div>
            )}
            {perf.return_current != null && (
              <div>
                <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Current Return</div>
                <div className={`text-2xl font-extrabold tracking-tight ${
                  perf.return_current >= 0 ? 'text-green-700' : 'text-red-800'
                }`}>
                  {perf.return_current >= 0 ? '↑ ' : '↓ '}{Math.abs(perf.return_current).toFixed(1)}%
                  <span className="text-sm font-normal text-gray-500 ml-1">
                    (${perf.price_current?.toFixed(2)})
                  </span>
                </div>
              </div>
            )}
            {perf.spy_return_90d != null && perf.return_day0 != null && (
              <div>
                <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Alpha vs SPY</div>
                <div className={`text-2xl font-extrabold tracking-tight ${
                  (perf.return_day0 - perf.spy_return_90d) >= 0 ? 'text-green-700' : 'text-red-800'
                }`}>
                  {(perf.return_day0 - perf.spy_return_90d) >= 0 ? '↑ ' : '↓ '}{Math.abs(perf.return_day0 - perf.spy_return_90d).toFixed(1)}%
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Hostile activist warning */}
      {data.has_hostile_activist && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-start gap-3">
          <span className="text-lg">⚠</span>
          <div>
            <div className="font-bold text-sm text-red-800">Hostile Activist Detected</div>
            <div className="text-sm text-red-700 mt-1">
              13D filing contains hostile language:
              {data.hostile_keywords && data.hostile_keywords.length > 0 && (
                <span className="ml-1">
                  {data.hostile_keywords.map((kw) => (
                    <span key={kw} className="inline-block bg-red-100 px-1.5 py-0.5 rounded text-xs font-semibold mx-0.5">
                      {kw}
                    </span>
                  ))}
                </span>
              )}
            </div>
            <div className="text-xs text-red-600 mt-1">
              88% of signals with hostile activist text underperform. Informational flag — not filtered.
            </div>
          </div>
        </div>
      )}

      {/* Buyers table */}
      {buyers.length > 0 && (
        <div className="mb-8">
          <h3 className="font-bold text-base mb-3">Who Bought</h3>

          {/* Desktop grid */}
          <div className="hidden md:block border-t-2 border-gray-900">
            {/* Header */}
            <div className="grid grid-cols-[1.5fr_1fr_80px_90px_100px_70px] gap-x-3 text-xs text-gray-600 uppercase tracking-wider py-2.5 border-b border-gray-200">
              <span>Name</span>
              <span>Title</span>
              <span>Shares</span>
              <span>Price</span>
              <span className="text-right">Value</span>
              <span className="text-right">Verify</span>
            </div>
            {/* Rows */}
            {buyers.map((buyer, i) => (
              <div
                key={i}
                className="grid grid-cols-[1.5fr_1fr_80px_90px_100px_70px] gap-x-3 py-3 border-b border-gray-100 items-center"
              >
                <div>
                  <span className="font-semibold">{buyer.name}</span>
                </div>
                <span className="text-gray-500 text-sm">{buyer.title || '—'}</span>
                <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {buyer.total_shares?.toLocaleString() || '—'}
                </span>
                <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {buyer.avg_price_per_share ? `$${buyer.avg_price_per_share.toFixed(2)}` : '—'}
                </span>
                <span className="text-right font-semibold" style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {formatValue(buyer.total_value)}
                </span>
                <span className="text-right">
                  {buyer.form4_url ? (
                    <a
                      href={buyer.form4_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-700 text-sm font-medium hover:text-blue-800"
                      onClick={(e) => e.stopPropagation()}
                    >
                      SEC →
                    </a>
                  ) : (
                    <span className="text-gray-300 text-sm">—</span>
                  )}
                </span>
              </div>
            ))}
          </div>

          {/* Mobile stacked cards */}
          <div className="md:hidden border-t-2 border-gray-900 divide-y divide-gray-100">
            {buyers.map((buyer, i) => (
              <div key={i} className="py-4">
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div className="min-w-0">
                    <div className="font-semibold text-sm truncate">{buyer.name}</div>
                    {buyer.title && (
                      <div className="text-xs text-gray-500 truncate">{buyer.title}</div>
                    )}
                  </div>
                  <div className="text-right">
                    <div className="font-semibold text-sm" style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {formatValue(buyer.total_value)}
                    </div>
                    {buyer.form4_url && (
                      <a
                        href={buyer.form4_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-700 text-xs font-medium hover:text-blue-800"
                        onClick={(e) => e.stopPropagation()}
                      >
                        SEC →
                      </a>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500" style={{ fontVariantNumeric: 'tabular-nums' }}>
                  <span>
                    <span className="text-gray-500">Shares:</span>{' '}
                    <span className="text-gray-700">{buyer.total_shares?.toLocaleString() || '—'}</span>
                  </span>
                  <span>
                    <span className="text-gray-500">Price:</span>{' '}
                    <span className="text-gray-700">
                      {buyer.avg_price_per_share ? `$${buyer.avg_price_per_share.toFixed(2)}` : '—'}
                    </span>
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-3 text-xs text-gray-500">
            "SEC →" links open the original Form 4 filing on sec.gov for verification.
          </div>
        </div>
      )}

      {/* Timeline */}
      {data.timeline && data.timeline.length > 0 && (
        <div>
          <h3 className="font-bold text-base mb-3">Trade Timeline</h3>
          <div className="space-y-2">
            {data.timeline.slice(0, 20).map((entry, i) => (
              <div key={i} className="flex gap-4 text-sm">
                <span className="text-gray-500 w-24 flex-shrink-0">{entry.date}</span>
                <span className={entry.notable ? 'font-semibold' : 'text-gray-600'}>
                  {entry.description}
                </span>
                {entry.form4_url && (
                  <a
                    href={entry.form4_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-700 text-xs hover:text-blue-800 flex-shrink-0"
                  >
                    SEC →
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
