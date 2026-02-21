import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { feedApi, profileApi, DbStats, SignalItem, ProfileSearchResult } from '../services/api'
import SignalCard from '../components/SignalCard'
import ProofWall from '../components/ProofWall'

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<DbStats | null>(null)
  const [topSignals, setTopSignals] = useState<SignalItem[]>([])
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
      const [statsRes, feedRes] = await Promise.allSettled([
        feedApi.getStats(),
        feedApi.getFeed(90, 4, 'medium'),
      ])
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
      if (feedRes.status === 'fulfilled') setTopSignals(feedRes.value.data.signals)
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
          92.7% Accuracy Detecting <span className="text-primary-600">Insider Patterns</span>
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto mb-6">
          When multiple insiders buy shares in a coordinated cluster, the stock moves +14.93% over
          the next 90 days on average. We detect these patterns and alert you before the announcement.
        </p>

        {/* Stats strip */}
        <div className="flex items-center justify-center gap-8 mb-4">
          <div>
            <div className="text-3xl font-bold text-gray-900">92.7%</div>
            <div className="text-sm text-gray-500">HIGH Hit Rate</div>
          </div>
          <div className="h-10 w-px bg-gray-200"></div>
          <div>
            <div className="text-3xl font-bold text-green-600">+14.93%</div>
            <div className="text-sm text-gray-500">Avg 90d Return</div>
          </div>
          <div className="h-10 w-px bg-gray-200"></div>
          <div>
            <div className="text-3xl font-bold text-gray-900">423</div>
            <div className="text-sm text-gray-500">Signals Tracked</div>
          </div>
          <div className="h-10 w-px bg-gray-200"></div>
          {stats && (
            <div>
              <div className="text-3xl font-bold text-gray-900">{stats.insider_transactions.toLocaleString()}</div>
              <div className="text-sm text-gray-500">Insider Trades Analyzed</div>
            </div>
          )}
        </div>
        <p className="text-xs text-gray-400 mb-8">
          Based on 41 scoreable HIGH signals.{' '}
          <Link to="/accuracy" className="text-primary-500 hover:text-primary-600 underline">See full accuracy data &rarr;</Link>
        </p>

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

      {/* ===== How It Works ===== */}
      <section className="mb-14">
        <h2 className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-6">How It Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Step 1 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">1</div>
            <h3 className="font-semibold text-gray-900 mb-2">Detect Insider Clusters</h3>
            <p className="text-sm text-gray-600">
              We monitor 52,000+ insider trades for coordinated buying patterns — when 3+ insiders
              buy within the same window, it's a 92.7% accurate predictor of a major event.
            </p>
          </div>
          {/* Step 2 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-green-100 text-green-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">2</div>
            <h3 className="font-semibold text-gray-900 mb-2">Confirm with Filings</h3>
            <p className="text-sm text-gray-600">
              Cross-reference with SEC 8-K filings — Material Agreements (Item 1.01) and governance
              changes confirm the insider pattern. The filing is the proof, not the signal.
            </p>
          </div>
          {/* Step 3 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">3</div>
            <h3 className="font-semibold text-gray-900 mb-2">Act with Conviction</h3>
            <p className="text-sm text-gray-600">
              Each signal gets a 30-second Decision Card — BUY, WATCH, or PASS — with the insider
              evidence, price action, and network connections behind it. Avg HIGH signal return: +14.93%.
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
            38/41 HIGH Hits &middot; 2 Misses &middot;{' '}
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
            <p className="text-sm text-gray-500">Top signals from the last 90 days</p>
          </div>
          <Link
            to="/signals"
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm font-medium"
          >
            View All Signals &rarr;
          </Link>
        </div>
        {topSignals.length === 0 ? (
          <p className="text-sm text-gray-500 py-8 text-center">No active signals in the last 90 days</p>
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
