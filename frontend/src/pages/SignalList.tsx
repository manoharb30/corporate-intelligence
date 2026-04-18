import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { snapshotApi, signalPerfApi, SnapshotSignal, DashboardStats } from '../services/api'

function formatValue(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`
  return `$${value.toLocaleString()}`
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function isHighConviction(signal: SnapshotSignal): boolean {
  return (
    signal.num_insiders <= 5 &&
    signal.total_value < 1_000_000 &&
    signal.conviction_tier === 'strong_buy'
  )
}

type ViewMode = '30d' | '60d' | '90d'

export default function SignalList() {
  const [viewMode, setViewMode] = useState<ViewMode>('30d')
  const [signals, setSignals] = useState<SnapshotSignal[]>([])
  const [heroStats, setHeroStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const daysMap: Record<ViewMode, number> = { '30d': 30, '60d': 60, '90d': 90 }

  useEffect(() => {
    let ignore = false
    setLoading(true)
    snapshotApi.getWeekly(daysMap[viewMode])
      .then((res) => {
        if (ignore) return
        const sorted = [...(res.data.signals || [])].sort(
          (a, b) => b.total_value - a.total_value
        )
        setSignals(sorted)
      })
      .catch(() => { if (!ignore) setSignals([]) })
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [viewMode])

  // Fetch precomputed dashboard stats (instant — single node read)
  useEffect(() => {
    signalPerfApi.getDashboardStats()
      .then((res) => { if (res.data && !('error' in res.data)) setHeroStats(res.data) })
      .catch(() => {})
  }, [])

  return (
    <div>
      {/* Hero Section */}
      <div className="mb-10">
        {/* Layer 1: Funnel stats */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-5 md:flex md:gap-12 mb-6">
          <div>
            <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Transactions Processed</div>
            <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">67,346</div>
          </div>
          <div>
            <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Genuine Purchases</div>
            <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">7,386</div>
          </div>
          <div>
            <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Companies Monitored</div>
            <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">5,437</div>
          </div>
          <div>
            <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Strong Buy Signals</div>
            <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">{heroStats?.total_signals || '—'}</div>
          </div>
        </div>

        {/* Layer 2: Claim stats — from precomputed blob */}
        {heroStats && (
          <div className="grid grid-cols-3 gap-x-6 md:flex md:gap-12 mb-4">
            <div>
              <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Hit Rate (90d)</div>
              <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                {heroStats.hit_rate}%
              </div>
            </div>
            <div>
              <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Alpha vs SPY</div>
              <div className="text-2xl sm:text-3xl font-extrabold tracking-tight text-green-700">
                +{heroStats.avg_alpha}%
              </div>
            </div>
            <div>
              <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Beat SPY</div>
              <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                {heroStats.beat_spy_pct}%
              </div>
            </div>
          </div>
        )}

        {/* Proof link */}
        <Link
          to="/performance"
          className="text-sm text-blue-700 font-medium hover:text-blue-800"
        >
          See the proof — track every signal →
        </Link>
      </div>

      {/* Divider */}
      <div className="border-t border-gray-200 mb-6" />

      {/* Signal cards header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div className="flex flex-wrap items-center gap-3 sm:gap-4">
          <h2 className="text-lg font-bold">Active Signals</h2>
          <div className="flex gap-1">
            {(['30d', '60d', '90d'] as ViewMode[]).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  viewMode === mode
                    ? 'bg-gray-900 text-white'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
              >
                {mode === '30d' ? 'Last 30d' : mode === '60d' ? 'Last 60d' : 'Last 90d'}
              </button>
            ))}
          </div>
        </div>
        {!loading && (
          <div className="text-sm text-gray-500">
            <strong className="text-gray-900">{signals.length}</strong> signals
          </div>
        )}
      </div>

      {/* Signal cards */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Loading...</div>
      ) : signals.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          No signals in the last {daysMap[viewMode]} days
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {signals.map((signal) => {
            const highConv = isHighConviction(signal)
            return (
              <a
                key={signal.accession_number}
                href={`/signal/${signal.accession_number}`}
                onClick={(e) => { if (!e.ctrlKey && !e.metaKey) { e.preventDefault(); navigate(`/signal/${signal.accession_number}`) } }}
                className="block bg-white border border-gray-200 rounded-lg p-4 cursor-pointer hover:bg-gray-50 transition-colors no-underline text-inherit"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-lg">{signal.ticker}</span>
                      <span className="text-gray-500 text-sm">{signal.company_name}</span>
                      {highConv ? (
                        <span className="bg-green-50 text-green-800 px-2 py-0.5 rounded text-xs font-bold uppercase">
                          High Conviction
                        </span>
                      ) : (
                        <span className="bg-gray-100 text-gray-500 px-2 py-0.5 rounded text-xs font-bold uppercase">
                          Standard
                        </span>
                      )}
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-sm text-gray-500">
                      <span>{signal.num_insiders} insiders bought</span>
                      <span className="text-gray-300">·</span>
                      <span>{formatDate(signal.signal_date)}</span>
                      <span className="text-gray-300">·</span>
                      <span className={signal.return_pct >= 0 ? 'text-green-700 font-semibold' : 'text-red-800 font-semibold'}>
                        {signal.return_pct >= 0 ? '↑' : '↓'} {Math.abs(signal.return_pct).toFixed(1)}%
                      </span>
                      {signal.alpha_pct != null && (
                        <>
                          <span className="text-gray-300">·</span>
                          <span className={signal.alpha_pct >= 0 ? 'text-green-700' : 'text-red-800'}>
                            α {signal.alpha_pct >= 0 ? '↑' : '↓'} {Math.abs(signal.alpha_pct).toFixed(1)}%
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-lg" style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {formatValue(signal.total_value)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      Day {signal.days_held}
                    </div>
                  </div>
                </div>
              </a>
            )
          })}
        </div>
      )}
    </div>
  )
}
