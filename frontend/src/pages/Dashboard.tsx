import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { feedApi, profileApi, dashboardApi, anomaliesApi, snapshotApi, DbStats, SignalItem, ProfileSearchResult, AccuracySummary, DashboardPulse, AnomalyItem, WeeklySnapshot, SnapshotSignal } from '../services/api'
import HistoricalContext, { getStats } from '../components/HistoricalContext'

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`
  return `$${v.toFixed(0)}`
}

function SignalRow({ signal, onClick }: { signal: SnapshotSignal; onClick: () => void }) {
  const isSell = signal.signal_action === 'PASS'
  const retColor = signal.return_pct >= 0 ? 'text-green-600' : 'text-red-600'
  const retSign = signal.return_pct >= 0 ? '+' : ''
  const action = isSell ? 'sold' : 'bought'
  const borderColor = isSell ? 'border-l-red-400' : 'border-l-green-400'

  return (
    <div
      onClick={onClick}
      className={`bg-white border border-gray-200 border-l-4 ${borderColor} rounded-xl p-5 hover:shadow-md cursor-pointer transition-all`}
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <span className="text-lg font-bold text-gray-900">{signal.ticker}</span>
          <span className="text-sm text-gray-500 ml-2">{signal.company_name}</span>
        </div>
        <div className="text-right">
          <div className={`text-sm font-bold ${isSell ? 'text-red-600' : 'text-green-600'}`}>
            {formatVolume(signal.total_value)} {action}
          </div>
          <div className="text-xs text-gray-400">
            {signal.num_insiders} insider{signal.num_insiders !== 1 ? 's' : ''} · {signal.days_held}d ago
          </div>
        </div>
      </div>
      {signal.reason && (
        <p className="text-sm text-gray-600 mb-2 leading-relaxed">{signal.reason}</p>
      )}
      <div className="flex items-center gap-3 text-xs mb-1">
        <span className={`font-semibold ${retColor}`}>{retSign}{signal.return_pct.toFixed(1)}% since signal</span>
        {signal.alpha_pct != null && (
          <span className={`${signal.alpha_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            ({signal.alpha_pct >= 0 ? '+' : ''}{signal.alpha_pct.toFixed(1)}% vs S&P 500)
          </span>
        )}
      </div>
      <HistoricalContext sicCode={signal.sic_code} direction={isSell ? 'sell' : 'buy'} variant="inline" />
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [, setStats] = useState<DbStats | null>(null)
  const [, setTopSignals] = useState<SignalItem[]>([])
  const [, setAccuracy] = useState<AccuracySummary | null>(null)
  const [, setPulse] = useState<DashboardPulse | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ProfileSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([])
  const [snapshot, setSnapshot] = useState<WeeklySnapshot | null>(null)
  const [showAllSells, setShowAllSells] = useState(false)
  const [showAllBuys, setShowAllBuys] = useState(false)
  const [showScorecard, setShowScorecard] = useState(false)

  useEffect(() => {
    let ignore = false
    const fetchData = async () => {
      setLoading(true)
      try {
        const preRes = await dashboardApi.getPrecomputed()
        if (ignore) return
        const data = preRes.data
        if (data.stats) setStats(data.stats as DbStats)
        if (data.signals) setTopSignals(data.signals)
        if (data.accuracy) setAccuracy(data.accuracy)
        if (data.pulse) setPulse(data.pulse)
        if (data.anomalies) setAnomalies(data.anomalies)
        if (data.scorecard) setSnapshot(data.scorecard)
      } catch {
        if (ignore) return
        try {
          const [statsRes, feedRes, pulseRes] = await Promise.allSettled([
            feedApi.getStats(),
            feedApi.getFeed(30, 100, 'medium'),
            dashboardApi.getPulse(),
          ])
          if (ignore) return
          if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
          if (feedRes.status === 'fulfilled') setTopSignals(feedRes.value.data.signals)
          if (pulseRes.status === 'fulfilled') setPulse(pulseRes.value.data)
        } catch (error) {
          if (!ignore) console.error('Failed to load:', error)
        }
      } finally {
        if (!ignore) setLoading(false)
      }
    }
    fetchData()
    return () => { ignore = true }
  }, [])

  // Fallback: if precomputed blob didn't include scorecard, fetch live
  useEffect(() => {
    if (snapshot || loading) return
    snapshotApi.getWeekly(30)
      .then(res => setSnapshot(res.data))
      .catch(() => {})
  }, [snapshot, loading])

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

  const sellSignals = snapshot?.signals?.filter(s => s.signal_action === 'PASS') || []
  const buySignals = snapshot?.signals?.filter(s => s.signal_action !== 'PASS') || []
  const bs = snapshot?.buy_stats
  const ss = snapshot?.sell_stats

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full"></div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">

      {/* ===== HERO: What's happening ===== */}
      <section className="py-10 mb-6">
        <h1 className="text-3xl font-extrabold text-gray-900 mb-3 tracking-tight">
          What Insiders Are Doing Right Now
        </h1>
        <p className="text-gray-500 mb-6 max-w-2xl">
          Corporate executives are required by law to report when they buy or sell
          their own company's stock. We monitor every filing and flag the ones that matter.
        </p>

        {/* Live counts */}
        {snapshot && (
          <div className="flex items-center gap-6 mb-8">
            {buySignals.length > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span className="text-sm text-gray-700">
                  <span className="font-bold text-green-700">{buySignals.length}</span> companies where insiders are buying
                </span>
              </div>
            )}
            {sellSignals.length > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <span className="text-sm text-gray-700">
                  <span className="font-bold text-red-700">{sellSignals.length}</span> companies where insiders are selling
                </span>
              </div>
            )}
            <span className="text-xs text-gray-400">Updated daily from SEC filings</span>
          </div>
        )}

        {/* Search bar */}
        <div className="relative max-w-lg">
          <input
            type="text"
            placeholder="Look up any public company..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-5 py-3 rounded-xl border border-gray-300 text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 shadow-sm text-base"
          />
          {searching && (
            <div className="absolute right-4 top-3.5">
              <div className="animate-spin h-5 w-5 border-2 border-primary-500 border-t-transparent rounded-full"></div>
            </div>
          )}
          {searchResults.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-xl shadow-xl border border-gray-200 z-50 max-h-64 overflow-y-auto">
              {searchResults.map(r => (
                <button
                  key={r.cik}
                  onClick={() => {
                    navigate(`/signals?cik=${r.cik}`)
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
      </section>

      {/* ===== INSIDERS ARE SELLING ===== */}
      {sellSignals.length > 0 && (
        <section className="mb-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-1 h-7 bg-red-500 rounded-full"></div>
            <h2 className="text-xl font-bold text-gray-900">Insiders Are Selling</h2>
            <span className="text-sm text-gray-400">Last 30 days</span>
          </div>

          <div className="space-y-3">
            {sellSignals
              .sort((a, b) => {
                const aHit = getStats(a.sic_code, 'sell').hit_rate
                const bHit = getStats(b.sic_code, 'sell').hit_rate
                if (bHit !== aHit) return bHit - aHit
                return (b.total_value || 0) - (a.total_value || 0)
              })
              .slice(0, showAllSells ? 20 : 5)
              .map((s, idx) => (
                <SignalRow
                  key={`sell-${s.cik}-${s.signal_date}-${idx}`}
                  signal={s}
                  onClick={() => navigate(`/signal/${encodeURIComponent(s.accession_number)}`)}
                />
              ))}
          </div>

          {sellSignals.length > 5 && (
            <button
              onClick={() => setShowAllSells(!showAllSells)}
              className="mt-3 text-sm text-red-600 hover:text-red-800 font-medium"
            >
              {showAllSells ? 'Show less' : `See all ${sellSignals.length} sell signals`}
            </button>
          )}
        </section>
      )}

      {/* ===== INSIDERS ARE BUYING ===== */}
      {buySignals.length > 0 && (
        <section className="mb-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-1 h-7 bg-green-500 rounded-full"></div>
            <h2 className="text-xl font-bold text-gray-900">Insiders Are Buying</h2>
            <span className="text-sm text-gray-400">Last 30 days</span>
          </div>

          <div className="space-y-3">
            {buySignals
              .sort((a, b) => {
                const aHit = getStats(a.sic_code, 'buy').hit_rate
                const bHit = getStats(b.sic_code, 'buy').hit_rate
                if (bHit !== aHit) return bHit - aHit
                return (b.total_value || 0) - (a.total_value || 0)
              })
              .slice(0, showAllBuys ? 20 : 5)
              .map((s, idx) => (
                <SignalRow
                  key={`buy-${s.cik}-${s.signal_date}-${idx}`}
                  signal={s}
                  onClick={() => navigate(`/signal/${encodeURIComponent(s.accession_number)}`)}
                />
              ))}
          </div>

          {buySignals.length > 5 && (
            <button
              onClick={() => setShowAllBuys(!showAllBuys)}
              className="mt-3 text-sm text-green-600 hover:text-green-800 font-medium"
            >
              {showAllBuys ? 'Show less' : `See all ${buySignals.length} buy signals`}
            </button>
          )}
        </section>
      )}

      {/* ===== HOW OUR SIGNALS PLAYED OUT ===== */}
      {(bs || ss) && (
        <section className="mb-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-1 h-7 bg-gray-800 rounded-full"></div>
            <h2 className="text-xl font-bold text-gray-900">How Our Signals Played Out</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            {/* Sell accuracy */}
            {ss && ss.total > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-5">
                <div className="text-sm font-semibold text-red-700 mb-2">Sell Signals</div>
                <div className="text-3xl font-black text-red-700 mb-1">
                  {ss.correct_rate !== null ? `${ss.correct_rate.toFixed(0)}%` : '—'}
                </div>
                <p className="text-sm text-red-600">
                  of the time, the stock dropped after we detected insider selling
                </p>
                <p className="text-xs text-gray-500 mt-2">
                  {ss.correct} out of {ss.total} signals correct
                </p>
              </div>
            )}

            {/* Buy performance */}
            {bs && bs.total > 0 && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-5">
                <div className="text-sm font-semibold text-green-700 mb-2">Buy Signals</div>
                <div className="text-3xl font-black text-green-700 mb-1">
                  {bs.beat_spy_count}/{bs.total}
                </div>
                <p className="text-sm text-green-600">
                  buy signals outperformed the S&P 500
                </p>
                {bs.avg_alpha !== null && (
                  <p className="text-xs text-gray-500 mt-2">
                    Average {bs.avg_alpha >= 0 ? '+' : ''}{bs.avg_alpha.toFixed(1)}% alpha vs S&P 500
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="text-center">
            <Link
              to="/accuracy"
              className="text-sm text-gray-500 hover:text-gray-700 font-medium underline"
            >
              See full track record
            </Link>
          </div>
        </section>
      )}

      {/* ===== PRE-EVENT INSIDER ACTIVITY ===== */}
      {anomalies.length > 0 && (
        <section className="mb-10">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-1 h-7 bg-purple-500 rounded-full"></div>
            <h2 className="text-xl font-bold text-gray-900">Insiders Who Sold Before the News</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4 ml-4">
            These insiders sold shares before a material event was publicly filed with the SEC.
          </p>

          <div className="space-y-3">
            {anomalies.slice(0, 5).map((a, idx) => (
              <div
                key={`anomaly-${a.cik}-${idx}`}
                onClick={() => navigate(`/signal/${encodeURIComponent(a.accession_number)}`)}
                className="bg-white border border-gray-200 border-l-4 border-l-purple-400 rounded-xl p-5 hover:shadow-md cursor-pointer transition-all"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <span className="text-lg font-bold text-gray-900">{a.ticker || '—'}</span>
                    <span className="text-sm text-gray-500 ml-2">{a.company_name}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-red-600">{formatVolume(a.pre_event_sell_value)} sold</div>
                    <div className="text-xs text-gray-400">before event</div>
                  </div>
                </div>
                <p className="text-sm text-gray-600">
                  {a.num_insiders} insider{a.num_insiders !== 1 ? 's' : ''} sold shares
                  {a.avg_days_before_event ? ` an average of ${Math.round(a.avg_days_before_event)} days` : ''} before
                  {' '}a {a.event_type === 'material_agreement' ? 'Material Agreement' :
                    a.event_type === 'executive_change' ? 'executive change' :
                    a.event_type === 'governance_change' ? 'governance change' :
                    a.event_type === 'acquisition_disposition' ? 'acquisition' :
                    'corporate event'} filing.
                </p>
              </div>
            ))}
          </div>

          {anomalies.length > 5 && (
            <div className="mt-3 flex items-center gap-4">
              <Link
                to="/signals?tab=intelligence"
                className="text-sm text-purple-600 hover:text-purple-800 font-medium"
              >
                See all {anomalies.length} events
              </Link>
              <a
                href={anomaliesApi.getDownloadUrl()}
                download
                className="text-sm text-gray-500 hover:text-gray-700 font-medium"
              >
                Download CSV
              </a>
            </div>
          )}
        </section>
      )}

      {/* ===== DETAILED SCORECARD (power users) ===== */}
      {snapshot && snapshot.signals.length > 0 && (
        <section className="mb-10">
          <button
            onClick={() => setShowScorecard(!showScorecard)}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-600 font-medium mb-4"
          >
            <span>{showScorecard ? 'Hide' : 'Show'} detailed signal performance</span>
            <span>{showScorecard ? '\u25B2' : '\u25BC'}</span>
          </button>

          {showScorecard && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Company</th>
                    <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                    <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Age</th>
                    <th className="text-right px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Entry</th>
                    <th className="text-right px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Current</th>
                    <th className="text-right px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Return</th>
                    <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Alpha</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.signals.slice(0, 30).map((s, idx) => {
                    const isSell = s.signal_action === 'PASS'
                    return (
                      <tr
                        key={`sc-${s.cik}-${s.signal_date}-${idx}`}
                        onClick={() => navigate(`/signal/${encodeURIComponent(s.accession_number)}`)}
                        className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
                      >
                        <td className="px-4 py-3">
                          <span className="font-bold text-gray-900">{s.ticker}</span>
                          <span className="text-gray-500 text-xs ml-2">{s.company_name}</span>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-bold ${
                            isSell ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                          }`}>
                            {isSell ? 'Sell' : 'Buy'}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-xs text-gray-600">{s.days_held}d</td>
                        <td className="px-3 py-3 text-right text-gray-600 font-mono text-xs">${s.entry_price.toFixed(2)}</td>
                        <td className="px-3 py-3 text-right text-gray-900 font-mono text-xs font-medium">${s.current_price.toFixed(2)}</td>
                        <td className="px-3 py-3 text-right">
                          <span className={`font-bold text-xs ${s.return_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {s.return_pct >= 0 ? '+' : ''}{s.return_pct.toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          {s.alpha_pct != null ? (
                            <span className={`text-xs font-bold ${s.alpha_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {s.alpha_pct >= 0 ? '+' : ''}{s.alpha_pct.toFixed(1)}%
                            </span>
                          ) : (
                            <span className="text-xs text-gray-300">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* ===== CTA ===== */}
      {/* ===== RESEARCH ===== */}
      <section className="mb-10">
        <Link
          to="/blog/insider-signal-research"
          className="block bg-gray-900 rounded-xl p-6 hover:bg-gray-800 transition-colors"
        >
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Research</div>
          <h3 className="text-lg font-bold text-white mb-2">
            We Tested 80+ Insider Trading Signal Definitions. Here's What Actually Works.
          </h3>
          <p className="text-sm text-gray-400">
            Banking insiders are right 89% of the time. "Buying the dip" is a myth. And more conviction doesn't mean better signals. Read the full analysis.
          </p>
        </Link>
      </section>

      {/* ===== CTA ===== */}
      <section className="text-center py-10 mb-8 border-t border-gray-100">
        <p className="text-gray-500 mb-6">Every signal is tracked with live prices. Nothing is backtested.</p>
        <div className="flex items-center justify-center gap-4 flex-wrap">
          <Link
            to="/accuracy"
            className="px-6 py-2.5 bg-gray-900 text-white rounded-lg hover:bg-gray-800 font-medium"
          >
            See Full Track Record
          </Link>
          <Link
            to="/signals"
            className="px-6 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
          >
            Browse All Signals
          </Link>
          <Link
            to="/pricing"
            className="px-6 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
          >
            Pricing
          </Link>
        </div>
      </section>
    </div>
  )
}
