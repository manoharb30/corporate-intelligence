import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { feedApi, profileApi, accuracyApi, dashboardApi, DbStats, SignalItem, ProfileSearchResult, AccuracySummary, DashboardPulse } from '../services/api'
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

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [statsRes, feedRes, accRes, pulseRes] = await Promise.allSettled([
        feedApi.getStats(),
        feedApi.getFeed(7, 10, 'medium'),
        accuracyApi.getSummary(),
        dashboardApi.getPulse(),
      ])
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
      if (feedRes.status === 'fulfilled') setTopSignals(feedRes.value.data.signals)
      if (accRes.status === 'fulfilled') setAccuracy(accRes.value.data)
      if (pulseRes.status === 'fulfilled') setPulse(pulseRes.value.data)
    } catch (error) {
      console.error('Failed to load:', error)
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

  const hitRate = accuracy?.overall_hit_rate ?? null
  const avgReturn = accuracy?.overall_avg_return_90d ?? null
  const totalSignals = accuracy?.total_signals ?? null
  const highStats = accuracy?.by_level?.high
  const mood = pulse?.market_mood
  const movers = pulse?.biggest_movers
  const week = pulse?.week_scorecard

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full"></div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto">

      {/* ===== Hero ===== */}
      <section className="text-center py-12 mb-8">
        <h1 className="text-4xl font-extrabold text-gray-900 mb-3 tracking-tight">
          {hitRate !== null ? `${hitRate.toFixed(1)}%` : '...'} Accuracy Detecting <span className="text-primary-600">Insider Patterns</span>
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto mb-6">
          When multiple insiders buy shares in a coordinated cluster, the stock moves
          {avgReturn !== null ? ` +${avgReturn.toFixed(2)}%` : ''} over
          the next 90 days on average. We detect these patterns and alert you before the announcement.
        </p>

        {/* Stats strip */}
        <div className="flex items-center justify-center gap-8 mb-4 flex-wrap">
          <div>
            <div className="text-3xl font-bold text-gray-900">{hitRate !== null ? `${hitRate.toFixed(1)}%` : '—'}</div>
            <div className="text-sm text-gray-500">HIGH Hit Rate</div>
          </div>
          <div className="h-10 w-px bg-gray-200 hidden sm:block"></div>
          <div>
            <div className="text-3xl font-bold text-green-600">{avgReturn !== null ? `+${avgReturn.toFixed(2)}%` : '—'}</div>
            <div className="text-sm text-gray-500">Avg 90d Return</div>
          </div>
          <div className="h-10 w-px bg-gray-200 hidden sm:block"></div>
          <div>
            <div className="text-3xl font-bold text-gray-900">{totalSignals !== null ? totalSignals.toLocaleString() : '—'}</div>
            <div className="text-sm text-gray-500">Signals Tracked</div>
          </div>
          <div className="h-10 w-px bg-gray-200 hidden sm:block"></div>
          {stats && (
            <div>
              <div className="text-3xl font-bold text-gray-900">{stats.insider_transactions.toLocaleString()}</div>
              <div className="text-sm text-gray-500">Insider Trades Analyzed</div>
            </div>
          )}
        </div>
        {highStats && (
          <p className="text-xs text-gray-400 mb-8">
            Based on {highStats.scoreable ?? highStats.count} scoreable HIGH signals.{' '}
            <Link to="/accuracy" className="text-primary-500 hover:text-primary-600 underline">See full accuracy data &rarr;</Link>
          </p>
        )}

        {/* Search bar */}
        <div className="relative max-w-lg mx-auto">
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
              <span className={`w-2.5 h-2.5 rounded-full ${pulse.last_signal.signal_type === 'insider_sell_cluster' ? 'bg-red-400' : 'bg-green-400'} animate-pulse`}></span>
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
                <>Scanning 13,000+ companies</>
              )}
            </div>
          </div>
        </section>
      )}

      {/* ===== Market Mood ===== */}
      {mood && (mood.buy_clusters > 0 || mood.sell_clusters > 0) && (
        <section className="mb-8">
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
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
        </section>
      )}

      {/* ===== Biggest Movers ===== */}
      {movers && (movers.top_gainer || movers.top_loser) && (
        <section className="mb-8">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Biggest Movers</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
        </section>
      )}

      {/* ===== Signal Ticker Strip ===== */}
      {topSignals.length > 0 && (
        <section className="mb-8">
          <div className="overflow-x-auto pb-2">
            <div className="flex gap-2 whitespace-nowrap">
              {topSignals.slice(0, 10).map((s, idx) => {
                const isSell = s.signal_type === 'insider_sell_cluster'
                const level = s.combined_signal_level || s.signal_level
                return (
                  <Link
                    key={`${s.accession_number}-${idx}`}
                    to={`/signal/${encodeURIComponent(s.accession_number)}`}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      level === 'critical' ? 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100' :
                      level === 'high_bearish' ? 'bg-red-50 text-red-600 border-red-200 hover:bg-red-100' :
                      level === 'high' ? 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100' :
                      'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      isSell ? 'bg-red-500' :
                      level === 'critical' ? 'bg-red-500' :
                      level === 'high' ? 'bg-amber-500' : 'bg-gray-400'
                    }`}></span>
                    {s.ticker || '?'} &middot; {s.signal_summary.length > 30 ? s.signal_summary.slice(0, 30) + '...' : s.signal_summary}
                  </Link>
                )
              })}
            </div>
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
            <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">1</div>
            <h3 className="font-semibold text-gray-900 mb-2">Detect Insider Clusters</h3>
            <p className="text-sm text-gray-600">
              We monitor {stats ? stats.insider_transactions.toLocaleString() : '86,000'}+ insider trades for coordinated buying patterns — when 3+ insiders
              buy within the same window, it's a {hitRate !== null ? `${hitRate.toFixed(1)}%` : 'highly'} accurate predictor of a major event.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-green-100 text-green-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">2</div>
            <h3 className="font-semibold text-gray-900 mb-2">Confirm with Filings</h3>
            <p className="text-sm text-gray-600">
              Cross-reference with SEC 8-K filings — Material Agreements (Item 1.01) and governance
              changes confirm the insider pattern. The filing is the proof, not the signal.
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">3</div>
            <h3 className="font-semibold text-gray-900 mb-2">Act with Conviction</h3>
            <p className="text-sm text-gray-600">
              Each signal gets a 30-second Decision Card — BUY, WATCH, or PASS — with the insider
              evidence, price action, and network connections behind it.{avgReturn !== null ? ` Avg HIGH signal return: +${avgReturn.toFixed(2)}%.` : ''}
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

      {/* ===== Live Signals ===== */}
      <section className="mb-14">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Live Right Now</h2>
            <p className="text-sm text-gray-500">Top signals from the last 7 days</p>
          </div>
          <Link
            to="/signals"
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm font-medium"
          >
            View All Signals &rarr;
          </Link>
        </div>
        {topSignals.length === 0 ? (
          <p className="text-sm text-gray-500 py-8 text-center">No active signals in the last 7 days</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {topSignals.slice(0, 4).map((signal, idx) => (
              <SignalCard key={`${signal.accession_number}-${idx}`} signal={signal} />
            ))}
          </div>
        )}
      </section>

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
            to="/signals"
            className="px-6 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
          >
            Browse Signals
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
