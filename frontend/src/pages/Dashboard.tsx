import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { feedApi, profileApi, DbStats, SignalItem, ProfileSearchResult } from '../services/api'
import SignalCard from '../components/SignalCard'

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
          Spot M&A Deals <span className="text-primary-600">Before</span> the Market
        </h1>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto mb-6">
          We monitor every SEC 8-K filing, cross-reference insider trading patterns,
          and surface the signals that matter — so you see the deal forming, not the headline.
        </p>

        {/* Stats strip */}
        {stats && (
          <div className="flex items-center justify-center gap-8 mb-8">
            <div>
              <div className="text-3xl font-bold text-gray-900">{stats.companies.toLocaleString()}</div>
              <div className="text-sm text-gray-500">Companies Tracked</div>
            </div>
            <div className="h-10 w-px bg-gray-200"></div>
            <div>
              <div className="text-3xl font-bold text-gray-900">{stats.events.toLocaleString()}</div>
              <div className="text-sm text-gray-500">8-K Filings Analyzed</div>
            </div>
            <div className="h-10 w-px bg-gray-200"></div>
            <div>
              <div className="text-3xl font-bold text-gray-900">{stats.insider_transactions.toLocaleString()}</div>
              <div className="text-sm text-gray-500">Insider Trades Mapped</div>
            </div>
          </div>
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

      {/* ===== How It Works ===== */}
      <section className="mb-14">
        <h2 className="text-center text-sm font-semibold text-gray-400 uppercase tracking-widest mb-6">How It Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Step 1 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">1</div>
            <h3 className="font-semibold text-gray-900 mb-2">Detect</h3>
            <p className="text-sm text-gray-600">
              We scan every SEC 8-K filing for Material Agreements (Item 1.01) combined with
              executive changes — the pattern that precedes 90% of M&A announcements.
            </p>
          </div>
          {/* Step 2 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-green-100 text-green-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">2</div>
            <h3 className="font-semibold text-gray-900 mb-2">Verify</h3>
            <p className="text-sm text-gray-600">
              Cross-reference with insider trading data — when executives buy heavily
              around a filing, it confirms conviction. We map every trade within 60 days.
            </p>
          </div>
          {/* Step 3 */}
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center shadow-sm">
            <div className="w-12 h-12 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center mx-auto mb-4 text-xl font-bold">3</div>
            <h3 className="font-semibold text-gray-900 mb-2">Act</h3>
            <p className="text-sm text-gray-600">
              Each signal gets a story page: the filing, insider evidence, price action,
              network connections, and a verdict — everything you need to make a decision.
            </p>
          </div>
        </div>
      </section>

      {/* ===== Proof Point — Splunk ===== */}
      <section className="mb-14">
        <div className="bg-gradient-to-r from-gray-900 to-primary-900 rounded-xl p-8 text-white">
          <div className="flex items-center gap-2 mb-3">
            <span className="px-2.5 py-1 bg-purple-600 rounded text-xs font-bold uppercase">Case Study</span>
          </div>
          <h3 className="text-xl font-bold mb-2">Splunk → Cisco Acquisition</h3>
          <p className="text-gray-300 leading-relaxed mb-4">
            In September 2023, Splunk filed an 8-K with Item 1.01 (Material Agreement) + Item 5.03
            (Governance Changes). Our system flagged it as <span className="text-red-400 font-semibold">HIGH</span>.
            Six months later, Cisco completed the $28B acquisition — one of the largest tech deals
            of the decade. Investors who acted on the filing had a 6-month head start.
          </p>
          <div className="flex items-center gap-6 text-sm">
            <div>
              <span className="text-gray-400">Filed:</span>{' '}
              <span className="font-medium">Sep 2023</span>
            </div>
            <div>
              <span className="text-gray-400">Completed:</span>{' '}
              <span className="font-medium">Mar 2024</span>
            </div>
            <div>
              <span className="text-gray-400">Lead Time:</span>{' '}
              <span className="font-semibold text-green-400">6 months</span>
            </div>
          </div>
          <Link
            to="/signal/0001104659-23-102594"
            className="inline-block mt-4 px-4 py-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-sm font-medium transition-colors"
          >
            See the full signal story &rarr;
          </Link>
        </div>
      </section>

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
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Ready to explore?</h2>
        <p className="text-gray-600 mb-6">Browse all signals, search any company, or see our plans for institutional access.</p>
        <div className="flex items-center justify-center gap-4 flex-wrap">
          <Link
            to="/signals"
            className="px-6 py-2.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 font-medium"
          >
            Browse Signals
          </Link>
          <Link
            to="/companies"
            className="px-6 py-2.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
          >
            Search Companies
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
