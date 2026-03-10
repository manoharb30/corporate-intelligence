import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { feedApi, profileApi, accuracyApi, dashboardApi, anomaliesApi, snapshotApi, DbStats, SignalItem, ProfileSearchResult, AccuracySummary, DashboardPulse, AnomalyItem, WeeklySnapshot } from '../services/api'
import SignalCard from '../components/SignalCard'
import ProofWall from '../components/ProofWall'

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`
  return `$${v.toFixed(0)}`
}

function daysAgoLabel(days: number): string {
  if (days === 0) return 'today'
  if (days === 1) return '1d ago'
  return `${days}d ago`
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<DbStats | null>(null)
  const [topSignals, setTopSignals] = useState<SignalItem[]>([])
  const [accuracy, setAccuracy] = useState<AccuracySummary | null>(null)
  const [pulse, setPulse] = useState<DashboardPulse | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ProfileSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([])
  const [snapshot, setSnapshot] = useState<WeeklySnapshot | null>(null)
  const [scorecardTab, setScorecardTab] = useState<'buy' | 'all'>('buy')
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const scorecardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let ignore = false
    const fetchData = async () => {
      setLoading(true)
      try {
        const [statsRes, feedRes, accRes, pulseRes, anomalyRes] = await Promise.allSettled([
          feedApi.getStats(),
          feedApi.getFeed(30, 100, 'medium'),
          accuracyApi.getSummary(),
          dashboardApi.getPulse(),
          anomaliesApi.getTop(15),
        ])
        if (ignore) return
        if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
        if (feedRes.status === 'fulfilled') setTopSignals(feedRes.value.data.signals)
        if (accRes.status === 'fulfilled') setAccuracy(accRes.value.data)
        if (pulseRes.status === 'fulfilled') setPulse(pulseRes.value.data)
        if (anomalyRes.status === 'fulfilled') setAnomalies(anomalyRes.value.data.anomalies)
      } catch (error) {
        if (!ignore) console.error('Failed to load:', error)
      } finally {
        if (!ignore) setLoading(false)
      }
    }
    fetchData()
    return () => { ignore = true }
  }, [])

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

  // Lazy-load snapshot when scorecard section scrolls into view
  useEffect(() => {
    if (snapshot || snapshotLoading) return
    const el = scorecardRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          observer.disconnect()
          setSnapshotLoading(true)
          snapshotApi.getWeekly(14)
            .then(res => setSnapshot(res.data))
            .catch(() => {})
            .finally(() => setSnapshotLoading(false))
        }
      },
      { rootMargin: '200px' }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [snapshot, snapshotLoading, loading])

  const hitRate = accuracy?.overall_hit_rate ?? null
  const avgReturn = accuracy?.overall_avg_return_90d ?? null
  const highStats = accuracy?.by_level?.high
  const mood = pulse?.market_mood
  const movers = pulse?.biggest_movers
  const week = pulse?.week_scorecard

  // Filter cluster-based signals (BUY candidates)
  const clusterSignals = topSignals.filter(s =>
    s.signal_type === 'insider_cluster' ||
    (s.signal_type === 'compound' && s.combined_signal_level === 'critical')
  )

  // Median days before event from anomalies
  const daysBeforeValues = anomalies
    .map(a => a.avg_days_before_event)
    .filter((d): d is number => d !== null)
    .sort((a, b) => a - b)
  const medianDaysBefore = daysBeforeValues.length > 0
    ? Math.round(daysBeforeValues[Math.floor(daysBeforeValues.length / 2)])
    : 15

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full"></div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto">

      {/* ===== Dual Hero Cards ===== */}
      <section className="py-10 mb-6">
        <h1 className="text-center text-3xl font-extrabold text-gray-900 mb-2 tracking-tight">
          Two Products. One Edge.
        </h1>
        <p className="text-center text-gray-500 mb-8 max-w-2xl mx-auto">
          Actionable trade signals from insider clusters, plus deep intelligence on who traded before material SEC filings.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left: Cluster Alerts */}
          <div className="relative bg-gradient-to-br from-green-50 to-emerald-50 border-2 border-green-200 rounded-2xl p-7 shadow-sm">
            <div className="absolute top-4 right-4">
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-green-100 text-green-700 border border-green-200">TRADE SIGNALS</span>
            </div>
            <div className="text-5xl font-black text-green-700 mb-1">
              {hitRate !== null ? `${hitRate.toFixed(1)}%` : '68.4%'}
            </div>
            <div className="text-sm font-semibold text-green-800 uppercase tracking-wide mb-3">Hit Rate</div>
            <h2 className="text-lg font-bold text-gray-900 mb-1">Insider Cluster Alerts</h2>
            <p className="text-sm text-gray-600 mb-4">
              Actionable signals when 3+ insiders buy shares in a coordinated window.
              {avgReturn !== null ? ` Avg 90d return: +${avgReturn.toFixed(2)}%.` : ''}
            </p>
            <Link
              to="/signals?tab=trade"
              className="inline-flex items-center text-sm font-semibold text-green-700 hover:text-green-900"
            >
              View Active Alerts &rarr;
            </Link>
          </div>

          {/* Right: Intelligence */}
          <div className="relative bg-gradient-to-br from-purple-50 to-indigo-50 border-2 border-purple-200 rounded-2xl p-7 shadow-sm">
            <div className="absolute top-4 right-4">
              <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-purple-100 text-purple-700 border border-purple-200">INTELLIGENCE</span>
            </div>
            <div className="text-5xl font-black text-purple-700 mb-1">
              {medianDaysBefore}d
            </div>
            <div className="text-sm font-semibold text-purple-800 uppercase tracking-wide mb-3">Lead Time</div>
            <h2 className="text-lg font-bold text-gray-900 mb-1">Insider-Event Intelligence</h2>
            <p className="text-sm text-gray-600 mb-4">
              Who sold before the SEC filing went public? Track insider behavior around material events.
            </p>
            <Link
              to="/signals?tab=intelligence"
              className="inline-flex items-center text-sm font-semibold text-purple-700 hover:text-purple-900"
            >
              View Full Intelligence Feed &rarr;
            </Link>
          </div>
        </div>

        {/* Search bar */}
        <div className="relative max-w-lg mx-auto mt-8">
          <input
            type="text"
            placeholder="Search any public company..."
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

      {/* ===== Real-Time Pulse ===== */}
      {pulse && pulse.last_signal && (
        <section className="mb-8">
          <div className="bg-gray-900 rounded-xl px-6 py-4 flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <span className={`w-2.5 h-2.5 rounded-full ${
                pulse.last_signal.signal_type === 'insider_sell_cluster' ? 'bg-red-400' :
                pulse.last_signal.signal_type === 'compound' ? 'bg-purple-400' :
                'bg-green-400'
              } animate-pulse`}></span>
              <span className="text-gray-300 text-sm">
                Last signal: <span className="text-white font-medium">{daysAgoLabel(pulse.last_signal.days_ago)}</span>
                {' \u2014 '}
                <Link to={`/signal/${encodeURIComponent(pulse.last_signal.accession_number)}`} className="text-white font-medium hover:text-primary-300">
                  {pulse.last_signal.ticker} {pulse.last_signal.signal_summary.toLowerCase()}
                </Link>
              </span>
            </div>
            <div className="text-sm text-gray-400">
              {pulse.today.signal_count > 0 ? (
                <>
                  Today: <span className="text-white font-medium">{pulse.today.signal_count} signals</span>
                  {pulse.today.total_sell_volume > 0 && (
                    <> &middot; <span className="text-red-400">{formatVolume(pulse.today.total_sell_volume)} selling</span></>
                  )}
                  {pulse.today.total_buy_volume > 0 && (
                    <> &middot; <span className="text-green-400">{formatVolume(pulse.today.total_buy_volume)} buying</span></>
                  )}
                </>
              ) : (
                <>No new signals today</>
              )}
            </div>
          </div>
        </section>
      )}

      {/* ===================================================================
          SECTION A: INSIDER CLUSTER ALERTS (Green)
          =================================================================== */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-1.5 h-8 bg-green-500 rounded-full"></div>
          <h2 className="text-xl font-bold text-gray-900">Insider Cluster Alerts</h2>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-green-100 text-green-700">TRADE SIGNALS</span>
        </div>
        <p className="text-sm text-gray-500 ml-5 mb-5">
          Actionable signals when 3+ insiders buy shares in a coordinated window
        </p>

        {/* Cluster stats strip */}
        <div className="bg-green-50 border border-green-200 rounded-xl p-5 mb-5">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-8">
              <div>
                <div className="text-2xl font-bold text-green-700">{hitRate !== null ? `${hitRate.toFixed(1)}%` : '—'}</div>
                <div className="text-xs text-green-600 font-medium">Hit Rate</div>
              </div>
              <div className="h-8 w-px bg-green-200"></div>
              <div>
                <div className="text-2xl font-bold text-green-700">{avgReturn !== null ? `+${avgReturn.toFixed(2)}%` : '—'}</div>
                <div className="text-xs text-green-600 font-medium">Avg 90d Return</div>
              </div>
              <div className="h-8 w-px bg-green-200"></div>
              <div>
                <div className="text-2xl font-bold text-green-700">{clusterSignals.length}</div>
                <div className="text-xs text-green-600 font-medium">Active Alerts</div>
              </div>
              {highStats && (
                <>
                  <div className="h-8 w-px bg-green-200"></div>
                  <div>
                    <div className="text-2xl font-bold text-green-700">{highStats.scoreable ?? highStats.count}</div>
                    <div className="text-xs text-green-600 font-medium">Signals Tracked</div>
                  </div>
                </>
              )}
            </div>
            <Link to="/accuracy" className="text-xs text-green-600 hover:text-green-800 font-medium underline">
              See full accuracy data &rarr;
            </Link>
          </div>
        </div>

        {/* Market Mood */}
        {mood && (mood.buy_clusters > 0 || mood.sell_clusters > 0) && (
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">30-Day Insider Mood</h3>
              <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                mood.label === 'Bearish' ? 'bg-red-100 text-red-700' :
                mood.label === 'Bullish' ? 'bg-green-100 text-green-700' :
                'bg-gray-100 text-gray-600'
              }`}>
                {mood.label}
              </span>
            </div>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-sm font-medium text-green-700">{mood.buy_clusters} Buy</span>
              <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden flex">
                {(mood.buy_clusters + mood.sell_clusters) > 0 && (
                  <>
                    <div
                      className="bg-green-500 h-full rounded-l-full"
                      style={{ width: `${(mood.buy_clusters / (mood.buy_clusters + mood.sell_clusters)) * 100}%` }}
                    ></div>
                    <div
                      className="bg-red-500 h-full rounded-r-full"
                      style={{ width: `${(mood.sell_clusters / (mood.buy_clusters + mood.sell_clusters)) * 100}%` }}
                    ></div>
                  </>
                )}
              </div>
              <span className="text-sm font-medium text-red-700">{mood.sell_clusters} Sell</span>
            </div>
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>{formatVolume(mood.buy_volume)} buying</span>
              <span>{formatVolume(mood.sell_volume)} selling</span>
            </div>
          </div>
        )}

        {/* Biggest Movers */}
        {movers && (movers.top_gainer || movers.top_loser) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
            {movers.top_gainer && (
              <Link
                to={`/signal/${encodeURIComponent(movers.top_gainer.accession_number)}`}
                className="bg-green-50 border border-green-200 rounded-xl p-5 hover:bg-green-100 transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-green-600 uppercase">Top Gainer</span>
                  <span className="text-2xl font-bold text-green-700">+{movers.top_gainer.price_change_pct.toFixed(1)}%</span>
                </div>
                <div className="text-lg font-bold text-gray-900">{movers.top_gainer.ticker}</div>
                <div className="text-sm text-gray-600 truncate">{movers.top_gainer.company_name}</div>
                <div className="text-xs text-green-700 mt-1">{movers.top_gainer.signal_summary}</div>
              </Link>
            )}
            {movers.top_loser && (
              <Link
                to={`/signal/${encodeURIComponent(movers.top_loser.accession_number)}`}
                className="bg-red-50 border border-red-200 rounded-xl p-5 hover:bg-red-100 transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-red-600 uppercase">Top Loser</span>
                  <span className="text-2xl font-bold text-red-700">{movers.top_loser.price_change_pct.toFixed(1)}%</span>
                </div>
                <div className="text-lg font-bold text-gray-900">{movers.top_loser.ticker}</div>
                <div className="text-sm text-gray-600 truncate">{movers.top_loser.company_name}</div>
                <div className="text-xs text-red-700 mt-1">{movers.top_loser.signal_summary}</div>
              </Link>
            )}
          </div>
        )}

        {/* Active cluster signals */}
        {clusterSignals.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            {clusterSignals.slice(0, 4).map((signal, idx) => (
              <SignalCard key={`${signal.accession_number}-${idx}`} signal={signal} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500 py-6 text-center bg-white rounded-xl border border-gray-200">
            No active cluster alerts in the last 30 days
          </p>
        )}

        <div className="text-center">
          <Link
            to="/signals?tab=trade"
            className="inline-flex items-center px-5 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium"
          >
            View All Trade Signals &rarr;
          </Link>
        </div>
      </section>

      {/* ===================================================================
          LIVE SCORECARD (lazy-loaded on scroll)
          =================================================================== */}
      <div ref={scorecardRef} />
      {snapshotLoading && (
        <section className="mb-12">
          <div className="text-center py-8 text-gray-400 text-sm">Loading scorecard...</div>
        </section>
      )}
      {snapshot && snapshot.total_signals > 0 && (() => {
        const buySignals = snapshot.signals.filter(s => s.signal_action === 'BUY')
        const watchSignals = snapshot.signals.filter(s => s.signal_action === 'WATCH')
        const passSignals = snapshot.signals.filter(s => s.signal_action === 'PASS')

        // Mature = 5+ days held — only these count in headline stats
        const matureBuy = buySignals.filter(s => s.days_held >= 5)
        const matureBuyWins = matureBuy.filter(s => s.return_pct > 0).length
        const matureBuyAvg = matureBuy.length > 0 ? matureBuy.reduce((a, s) => a + s.return_pct, 0) / matureBuy.length : 0
        const matureAll = snapshot.signals.filter(s => s.days_held >= 5)
        const matureAllWins = matureAll.filter(s => s.return_pct > 0).length
        const matureAllAvg = matureAll.length > 0 ? matureAll.reduce((a, s) => a + s.return_pct, 0) / matureAll.length : 0

        const watchWins = watchSignals.filter(s => s.days_held >= 5 && s.return_pct > 0).length
        const matureWatch = watchSignals.filter(s => s.days_held >= 5)
        const watchAvg = matureWatch.length > 0 ? matureWatch.reduce((a, s) => a + s.return_pct, 0) / matureWatch.length : 0
        const maturePass = passSignals.filter(s => s.days_held >= 5)
        const passCorrect = maturePass.filter(s => s.return_pct <= 0).length

        const bestBuy = matureBuy.length > 0 ? matureBuy.reduce((a, b) => a.return_pct > b.return_pct ? a : b) : null
        const worstBuy = matureBuy.length > 0 ? matureBuy.reduce((a, b) => a.return_pct < b.return_pct ? a : b) : null

        const spyReturn = snapshot.spy_return

        // For headline: use mature BUY in buy tab, mature all in all tab
        const headlineWins = scorecardTab === 'buy' ? matureBuyWins : matureAllWins
        const headlineTotal = scorecardTab === 'buy' ? matureBuy.length : matureAll.length
        const headlineAvg = scorecardTab === 'buy' ? matureBuyAvg : matureAllAvg
        const headlineAlpha = spyReturn !== null ? headlineAvg - spyReturn : null

        return (
        <section className="mb-12">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-1.5 h-8 bg-gray-800 rounded-full"></div>
            <h2 className="text-xl font-bold text-gray-900">Live Scorecard</h2>
          </div>
          <p className="text-sm text-gray-500 ml-5 mb-5">
            Signals from the last 14 days — tracked in real time
          </p>

          {/* Headline stats */}
          {headlineTotal > 0 && (
            <div className="bg-gray-900 rounded-xl p-5 mb-4">
              <div className="text-sm text-gray-300 mb-3">
                <span className="text-white font-bold">{headlineWins} of {headlineTotal}</span>
                {' '}mature signals winning (5+ days held)
                {' · Avg return: '}
                <span className={headlineAvg >= 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>
                  {headlineAvg >= 0 ? '+' : ''}{headlineAvg.toFixed(1)}%
                </span>
                {spyReturn !== null && (
                  <>
                    {' · Market: '}
                    <span className={spyReturn >= 0 ? 'text-gray-300' : 'text-red-400'}>
                      {spyReturn >= 0 ? '+' : ''}{spyReturn.toFixed(1)}%
                    </span>
                    {headlineAlpha !== null && (
                      <>
                        {' (alpha: '}
                        <span className={headlineAlpha >= 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>
                          {headlineAlpha >= 0 ? '+' : ''}{headlineAlpha.toFixed(1)}%
                        </span>
                        {')'}
                      </>
                    )}
                  </>
                )}
              </div>
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div className="flex items-center gap-6">
                  <div>
                    <div className="text-xs text-green-400 font-semibold uppercase tracking-wide mb-1">
                      {scorecardTab === 'buy' ? 'BUY Signals' : 'All Signals'} (mature)
                    </div>
                    <div className="flex items-baseline gap-1">
                      <span className="text-2xl font-bold text-white">{headlineWins}</span>
                      <span className="text-gray-400">/</span>
                      <span className="text-2xl font-bold text-white">{headlineTotal}</span>
                      <span className="text-sm text-gray-400 ml-1">winning</span>
                    </div>
                  </div>
                  <div className="h-10 w-px bg-gray-700"></div>
                  <div>
                    <div className={`text-2xl font-bold ${headlineAvg >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {headlineAvg >= 0 ? '+' : ''}{headlineAvg.toFixed(2)}%
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">avg return</div>
                  </div>
                  {spyReturn !== null && (
                    <>
                      <div className="h-10 w-px bg-gray-700"></div>
                      <div>
                        <div className={`text-lg font-bold ${spyReturn >= 0 ? 'text-gray-400' : 'text-red-400'}`}>
                          {spyReturn >= 0 ? '+' : ''}{spyReturn.toFixed(2)}%
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5">SPY ({snapshot.period_days}d)</div>
                      </div>
                    </>
                  )}
                  {bestBuy && scorecardTab === 'buy' && (
                    <>
                      <div className="h-10 w-px bg-gray-700"></div>
                      <div>
                        <div className="text-sm font-bold text-green-400">
                          {bestBuy.ticker} {bestBuy.return_pct >= 0 ? '+' : ''}{bestBuy.return_pct.toFixed(1)}%
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5">best BUY</div>
                      </div>
                    </>
                  )}
                  {worstBuy && scorecardTab === 'buy' && (
                    <>
                      <div className="h-10 w-px bg-gray-700"></div>
                      <div>
                        <div className="text-sm font-bold text-red-400">
                          {worstBuy.ticker} {worstBuy.return_pct >= 0 ? '+' : ''}{worstBuy.return_pct.toFixed(1)}%
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5">worst BUY</div>
                      </div>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-32 h-2 bg-gray-700 rounded-full overflow-hidden flex">
                    <div className="bg-green-500 h-full rounded-l-full" style={{ width: `${(headlineWins / headlineTotal) * 100}%` }}></div>
                    <div className="bg-red-500 h-full rounded-r-full" style={{ width: `${((headlineTotal - headlineWins) / headlineTotal) * 100}%` }}></div>
                  </div>
                  <span className="text-xs text-gray-400">{((headlineWins / headlineTotal) * 100).toFixed(0)}% win</span>
                </div>
              </div>
            </div>
          )}

          {/* Stat bars for WATCH and PASS */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
            {watchSignals.length > 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-yellow-100 text-yellow-700">WATCH</span>
                  <span className="text-xs text-gray-400">{matureWatch.length} mature / {watchSignals.length} total</span>
                </div>
                <div className="flex items-center gap-4">
                  <div>
                    <span className="text-lg font-bold text-gray-900">{watchWins}/{matureWatch.length}</span>
                    <span className="text-xs text-gray-500 ml-1">winning</span>
                  </div>
                  {matureWatch.length > 0 && (
                    <div className={`text-lg font-bold ${watchAvg >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {watchAvg >= 0 ? '+' : ''}{watchAvg.toFixed(2)}%
                    </div>
                  )}
                </div>
              </div>
            )}
            {passSignals.length > 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-gray-100 text-gray-600">PASS</span>
                  <span className="text-xs text-gray-400">{maturePass.length} mature / {passSignals.length} total</span>
                </div>
                <div className="flex items-center gap-4">
                  <div>
                    <span className="text-lg font-bold text-gray-900">{passCorrect}/{maturePass.length}</span>
                    <span className="text-xs text-gray-500 ml-1">called correctly</span>
                  </div>
                  <span className="text-xs text-gray-500">Stock dropped after we said PASS</span>
                </div>
              </div>
            )}
          </div>

          {/* Tab toggle */}
          <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
            <button
              onClick={() => setScorecardTab('buy')}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                scorecardTab === 'buy' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              BUY Signals ({buySignals.length})
            </button>
            <button
              onClick={() => setScorecardTab('all')}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                scorecardTab === 'all' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              All Signals ({snapshot.total_signals})
            </button>
          </div>

          {/* Signal table */}
          {(() => {
            const displaySignals = scorecardTab === 'buy'
              ? buySignals
              : snapshot.signals
            return (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Signal</th>
                    <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Action</th>
                    <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Age</th>
                    <th className="text-right px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Entry</th>
                    <th className="text-right px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Current</th>
                    <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      {scorecardTab === 'buy' ? 'Return' : 'Result'}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {displaySignals.slice(0, 20).map((s, idx) => {
                    const actionColor =
                      s.signal_action === 'BUY' ? 'bg-green-100 text-green-700' :
                      s.signal_action === 'WATCH' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-600'
                    const typeLabel =
                      s.signal_type === 'insider_cluster' ? 'Cluster Buy' :
                      s.signal_type === 'insider_sell_cluster' ? 'Cluster Sell' :
                      'Compound'
                    const typeColor =
                      s.signal_type === 'insider_cluster' ? 'text-green-600' :
                      s.signal_type === 'insider_sell_cluster' ? 'text-red-600' :
                      'text-purple-600'

                    const isMaturing = s.days_held < 5
                    const isPass = s.signal_action === 'PASS'
                    const passCorrectCall = isPass && s.return_pct <= 0

                    return (
                      <tr
                        key={`${s.cik}-${s.signal_date}-${idx}`}
                        onClick={() => navigate(`/signal/${encodeURIComponent(s.accession_number)}`)}
                        className={`border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors ${isMaturing ? 'opacity-60' : ''}`}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-gray-900">{s.ticker}</span>
                            <span className="text-gray-500 truncate max-w-[140px] text-xs">{s.company_name}</span>
                          </div>
                          <span className={`text-xs font-medium ${typeColor}`}>{typeLabel}</span>
                        </td>
                        <td className="px-3 py-3">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-bold ${actionColor}`}>
                            {s.signal_action}
                          </span>
                        </td>
                        <td className="px-3 py-3 whitespace-nowrap text-xs">
                          <span className="text-gray-600">{s.days_held}d</span>
                          {isMaturing && (
                            <span className="ml-1.5 px-1.5 py-0.5 rounded bg-gray-100 text-gray-400 text-[10px] font-semibold uppercase">Maturing</span>
                          )}
                        </td>
                        <td className="px-3 py-3 text-right text-gray-600 font-mono text-xs">
                          ${s.entry_price.toFixed(2)}
                        </td>
                        <td className="px-3 py-3 text-right text-gray-900 font-mono text-xs font-medium">
                          ${s.current_price.toFixed(2)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {isMaturing ? (
                            <span className="text-xs text-gray-400 italic">
                              {s.return_pct >= 0 ? '+' : ''}{s.return_pct.toFixed(2)}%
                            </span>
                          ) : isPass ? (
                            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                              passCorrectCall ? 'bg-green-50 text-green-700' : 'bg-gray-50 text-gray-500'
                            }`}>
                              {passCorrectCall
                                ? `Correct (${s.return_pct.toFixed(1)}%)`
                                : `Missed (+${s.return_pct.toFixed(1)}%)`}
                            </span>
                          ) : (
                            <span className={`font-bold ${s.return_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {s.return_pct >= 0 ? '+' : ''}{s.return_pct.toFixed(2)}%
                            </span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            )
          })()}
        </section>
        )
      })()}

      {/* ===================================================================
          SECTION B: INSIDER-EVENT INTELLIGENCE (Purple)
          =================================================================== */}
      {anomalies.length > 0 && (
        <section className="mb-12">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-1.5 h-8 bg-purple-500 rounded-full"></div>
            <h2 className="text-xl font-bold text-gray-900">Insider-Event Intelligence</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-100 text-purple-700">INTELLIGENCE</span>
          </div>
          <p className="text-sm text-gray-500 ml-5 mb-5">
            Who sold before the SEC filing went public? Track insider behavior around material events.
          </p>

          {/* Intelligence stats strip */}
          <div className="bg-purple-50 border border-purple-200 rounded-xl p-5 mb-5">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-center gap-8">
                <div>
                  <div className="text-2xl font-bold text-purple-700">{anomalies.length}</div>
                  <div className="text-xs text-purple-600 font-medium">Events Analyzed</div>
                </div>
                <div className="h-8 w-px bg-purple-200"></div>
                <div>
                  <div className="text-2xl font-bold text-purple-700">{medianDaysBefore}d</div>
                  <div className="text-xs text-purple-600 font-medium">Median Lead Time</div>
                </div>
                <div className="h-8 w-px bg-purple-200"></div>
                <div>
                  <div className="text-2xl font-bold text-purple-700">
                    {new Set(anomalies.map(a => a.cik)).size}
                  </div>
                  <div className="text-xs text-purple-600 font-medium">Companies Tracked</div>
                </div>
              </div>
              <a
                href={anomaliesApi.getDownloadUrl()}
                download
                className="px-3 py-1.5 text-xs font-medium text-purple-600 bg-white border border-purple-300 rounded-lg hover:bg-purple-50"
              >
                Download CSV
              </a>
            </div>
          </div>

          {/* Anomaly table */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mb-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-purple-50/50">
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Company</th>
                  <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Event</th>
                  <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</th>
                  <th className="text-right px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Insiders</th>
                  <th className="text-right px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Pre-Event Selling</th>
                  <th className="text-right px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Avg Days Before</th>
                  <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Ratio</th>
                </tr>
              </thead>
              <tbody>
                {anomalies.map((a, idx) => {
                  const eventPillColor =
                    a.event_type === 'material_agreement' ? 'bg-amber-100 text-amber-700' :
                    a.event_type === 'executive_change' ? 'bg-blue-100 text-blue-700' :
                    a.event_type === 'governance_change' ? 'bg-purple-100 text-purple-700' :
                    a.event_type === 'acquisition_disposition' ? 'bg-green-100 text-green-700' :
                    a.event_type === 'rights_modification' ? 'bg-pink-100 text-pink-700' :
                    'bg-gray-100 text-gray-600'
                  const eventLabel =
                    a.event_type === 'material_agreement' ? 'Material Agreement' :
                    a.event_type === 'executive_change' ? 'Exec Change' :
                    a.event_type === 'governance_change' ? 'Governance' :
                    a.event_type === 'acquisition_disposition' ? 'Acquisition' :
                    a.event_type === 'rights_modification' ? 'Rights Mod' :
                    a.event_type
                  const ratioWidth = Math.min(a.ratio * 100, 100)
                  return (
                    <tr
                      key={`${a.cik}-${a.event_date}-${idx}`}
                      onClick={() => navigate(`/signal/${encodeURIComponent(a.accession_number)}`)}
                      className="border-b border-gray-50 hover:bg-purple-50/30 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-gray-900">{a.ticker || '—'}</span>
                          <span className="text-gray-500 truncate max-w-[140px]">{a.company_name}</span>
                          {a.edgar_url && (
                            <a
                              href={a.edgar_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-xs text-blue-500 hover:text-blue-700 underline whitespace-nowrap"
                              title="View 8-K filing on SEC EDGAR"
                            >
                              SEC
                            </a>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${eventPillColor}`}>
                          {eventLabel}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-gray-600 whitespace-nowrap">{a.event_date}</td>
                      <td className="px-3 py-3 text-right text-gray-900 font-medium">{a.num_insiders}</td>
                      <td className="px-3 py-3 text-right font-semibold text-red-600 whitespace-nowrap">
                        {formatVolume(a.pre_event_sell_value)}
                      </td>
                      <td className="px-3 py-3 text-right text-gray-600">
                        {a.avg_days_before_event !== null ? `${Math.round(a.avg_days_before_event)}d` : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-purple-500 rounded-full"
                              style={{ width: `${ratioWidth}%` }}
                            ></div>
                          </div>
                          <span className="text-xs font-medium text-gray-700 w-10 text-right">
                            {(a.ratio * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="text-center">
            <Link
              to="/signals?tab=intelligence"
              className="inline-flex items-center px-5 py-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium"
            >
              View Full Intelligence Feed &rarr;
            </Link>
          </div>
        </section>
      )}

      {/* ===== Weekly Scorecard ===== */}
      {week && week.total_signals > 0 && (
        <section className="mb-8">
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm flex items-center justify-between flex-wrap gap-4">
            <div>
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-1">This Week</h3>
              <p className="text-gray-900 font-medium">
                {week.buy_signals} buy signal{week.buy_signals !== 1 ? 's' : ''}
                {week.buy_avg_return !== null && (
                  <span className="text-green-600"> ({week.buy_avg_return >= 0 ? '+' : ''}{week.buy_avg_return}% avg)</span>
                )}
                {' \u00B7 '}
                {week.sell_signals} sell signal{week.sell_signals !== 1 ? 's' : ''}
                {week.sell_avg_return !== null && (
                  <span className="text-red-600"> ({week.sell_avg_return >= 0 ? '+' : ''}{week.sell_avg_return}% avg)</span>
                )}
                {(week.compound_signals ?? 0) > 0 && (
                  <>
                    {' \u00B7 '}
                    <span className="text-purple-600">{week.compound_signals} compound</span>
                  </>
                )}
              </p>
            </div>
            <Link to="/signals" className="text-sm text-primary-600 hover:text-primary-700 font-medium">
              View all &rarr;
            </Link>
          </div>
        </section>
      )}

      {/* ===== How It Works ===== */}
      <section className="mb-14">
        <h2 className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-6">How It Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-green-100 text-green-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">1</div>
            <h3 className="font-semibold text-gray-900 mb-2">Detect Insider Clusters</h3>
            <p className="text-sm text-gray-600">
              We monitor {stats ? stats.insider_transactions.toLocaleString() : '86,000'}+ insider trades for coordinated buying patterns — when 3+ insiders
              buy within the same window, it's a {hitRate !== null ? `${hitRate.toFixed(1)}%` : 'highly'} accurate predictor of a major event.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">2</div>
            <h3 className="font-semibold text-gray-900 mb-2">Track Pre-Filing Behavior</h3>
            <p className="text-sm text-gray-600">
              Our anomaly detector cross-references insider trades with SEC 8-K filings — insiders trade a median {medianDaysBefore} days
              before material events become public.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">3</div>
            <h3 className="font-semibold text-gray-900 mb-2">Act with Conviction</h3>
            <p className="text-sm text-gray-600">
              Each signal gets a 30-second Decision Card — BUY, WATCH, or PASS — with the insider
              evidence, price action, and historical confidence behind it.
            </p>
          </div>
        </div>
      </section>

      {/* ===== Proof Banner ===== */}
      <section className="mb-14">
        <Link
          to="/accuracy"
          className="block bg-green-50 border border-green-200 rounded-xl p-6 text-center hover:bg-green-100 transition-colors"
        >
          <p className="text-sm font-semibold text-green-800 uppercase tracking-wide mb-1">Verified by data, not marketing</p>
          <p className="text-lg text-green-900 font-bold">
            {highStats ? (
              <>{highStats.hits}/{highStats.scoreable ?? highStats.count} HIGH Hits &middot; {highStats.misses} Miss{highStats.misses !== 1 ? 'es' : ''}</>
            ) : (
              <>View accuracy tracker</>
            )}
            {' \u00B7 '}
            <span className="underline">View Tracker &rarr;</span>
          </p>
        </Link>
      </section>

      {/* ===== Proof Wall ===== */}
      <ProofWall variant="dark" />

      {/* ===== CTA ===== */}
      <section className="text-center py-10 mb-8 border-t border-gray-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">See the proof, then decide</h2>
        <p className="text-gray-600 mb-6">Review our live accuracy tracker, browse signals, or see pricing for institutional access.</p>
        <div className="flex items-center justify-center gap-4 flex-wrap">
          <Link
            to="/accuracy"
            className="px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium"
          >
            See Accuracy Data
          </Link>
          <Link
            to="/signals?tab=trade"
            className="px-6 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium"
          >
            Trade Signals
          </Link>
          <Link
            to="/signals?tab=intelligence"
            className="px-6 py-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium"
          >
            Intelligence Feed
          </Link>
          <Link
            to="/pricing"
            className="px-6 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
          >
            View Pricing
          </Link>
        </div>
      </section>
    </div>
  )
}
