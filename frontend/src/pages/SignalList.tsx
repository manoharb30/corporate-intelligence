import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { snapshotApi, signalPerfApi, SnapshotSignal, DashboardStats, CoverageStats } from '../services/api'

function formatValue(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`
  return `$${value.toLocaleString()}`
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// "High Conviction" = backend signal_level='high' (3+ distinct buyers).
// The snapshot response doesn't carry signal_level directly; num_insiders is the 1:1 proxy
// since the backend rule is exactly num_insiders >= 3 → 'high'.
// 2 buyers IS the strong_buy bar, so badging those "MEDIUM CONVICTION" argued against the
// page's own headline. Only 3+ earns a badge now; 2 shows none, and the buyer count is
// already stated in the row metadata directly beneath.
function isHighConviction(signal: SnapshotSignal): boolean {
  return signal.num_insiders >= 3 && signal.conviction_tier === 'strong_buy'
}

type ViewMode = '30d' | '60d' | '90d'

export default function SignalList() {
  const [viewMode, setViewMode] = useState<ViewMode>('30d')
  const [signals, setSignals] = useState<SnapshotSignal[]>([])
  const [coverage, setCoverage] = useState<CoverageStats | null>(null)
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

    signalPerfApi
      .getCoverageStats()
      .then((r) => setCoverage(r.data))
      .catch(() => {})
  }, [])

  return (
    <div>
      {/* Dark hero band, pulled flush with the navy nav (-mt-6/-mx-*) so the top of the
          page reads as one deliberate region rather than text on white. Most visitors now
          arrive from outbound email and have never seen the product. */}
      <div
        className="-mt-6 bg-primary-800 text-white"
        /* True full-bleed: the page container is mx-auto max-w-7xl, so negative padding
           margins alone leave white gutters at wide viewports and the band stops short of
           the nav above it. calc(50% - 50vw) escapes the container on both sides. */
        style={{ marginLeft: 'calc(50% - 50vw)', marginRight: 'calc(50% - 50vw)' }}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
            High-conviction insider buying, filtered from SEC Form&nbsp;4 filings
          </h1>
          <p className="mt-4 text-base sm:text-lg text-gray-300 leading-relaxed">
            Most insider &ldquo;buying&rdquo; isn&rsquo;t a decision to buy. We separate genuine
            open-market purchases from RSU vesting, dividend reinvestment, private placements
            and structured allocations &mdash; then surface only the cases where several
            insiders bought together.
          </p>

          {/* Funnel as proportional bars. Widths are the REAL ratios against
              transactions analysed — no floor, no schematic scaling — which is why the
              signals bar is a sliver: only ~1% survives. That brutality IS the pitch, so
              faking a readable width would throw away the argument.
              Companies covered sits ABOVE the bars, not in them: it is a different unit
              and not a filter stage, and bar-charting it beside transactions would imply
              a subset relationship that runs backwards. */}
          <div className="mt-10">
            <div className="flex items-baseline gap-2 pb-5 mb-5 border-b border-white/10">
              <span className="text-xl font-bold tracking-tight tabular-nums">
                {coverage ? coverage.companies_covered.toLocaleString() : '\u2014'}
              </span>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                companies covered
              </span>
            </div>

            {coverage && coverage.transactions_analysed > 0 && (
              <div className="space-y-4">
                {([
                  {
                    label: 'Transactions analysed',
                    value: coverage.transactions_analysed,
                    bar: 'bg-blue-300/70',
                    text: '',
                    note: '',
                  },
                  {
                    label: 'Genuine purchases',
                    value: coverage.genuine_purchases,
                    bar: 'bg-blue-200/80',
                    text: '',
                    note: `\u2212${Math.round(
                      (1 - coverage.genuine_purchases / coverage.transactions_analysed) * 100
                    )}% rejected \u00b7 RSU vesting, DRIP, placements, structured deals`,
                  },
                  {
                    label: 'Strong-buy signals',
                    value: heroStats?.total_signals ?? 0,
                    bar: 'bg-green-400',
                    text: 'text-green-400',
                    note: '',
                  },
                ] as const).map((row) => {
                  const pct = (row.value / coverage.transactions_analysed) * 100
                  return (
                    <div key={row.label}>
                      <div className="flex flex-wrap items-baseline gap-x-3">
                        <span
                          className={`text-2xl sm:text-3xl font-extrabold tracking-tight tabular-nums ${row.text}`}
                        >
                          {row.value ? row.value.toLocaleString() : '\u2014'}
                        </span>
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                          {row.label}
                        </span>
                        {row.note && (
                          <span className="text-xs text-gray-400">{row.note}</span>
                        )}
                      </div>
                      <div className="mt-1.5 h-2 w-full rounded-sm bg-white/5 overflow-hidden">
                        <div
                          className={`h-full rounded-sm ${row.bar}`}
                          style={{ width: `${Math.max(pct, 0.4)}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Claim stats — dated, because these move every time a signal matures. */}
          {heroStats && (
            <div className="mt-8 pt-6 border-t border-white/15 flex flex-wrap items-end gap-x-10 gap-y-4">
              <div>
                <div className="text-2xl sm:text-3xl font-extrabold tracking-tight tabular-nums">
                  {heroStats.hit_rate}%
                </div>
                <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                  Hit rate (90d)
                </div>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-extrabold tracking-tight tabular-nums text-green-400">
                  +{heroStats.avg_alpha}pp
                </div>
                <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                  Alpha vs SPY
                </div>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-extrabold tracking-tight tabular-nums">
                  {heroStats.beat_spy_pct}%
                </div>
                <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                  Beat SPY
                </div>
              </div>
              {heroStats.computed_at && (
                /* ml-auto anchors this to the right edge of the band. Floating it mid-row
                   read as an accident; the numbers move on every maturation, so the date
                   has to be visible but subordinate. */
                <div className="w-full sm:w-auto sm:ml-auto text-xs text-gray-300 pb-1 sm:text-right">
                  Track record as of{' '}
                  {new Date(heroStats.computed_at).toLocaleDateString('en-GB', {
                    day: 'numeric', month: 'short', year: 'numeric',
                  })}
                  <div className="text-gray-400">{heroStats.total_signals} matured signals</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Supporting detail on light — the gate, and the method claims. */}
      <div className="py-8">
        <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 mb-5">
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider mb-2">
            A strong-buy signal requires all four
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-8 gap-y-1.5 text-sm text-gray-800">
            <div><span className="font-semibold">2+ distinct insiders</span> buying within 30 days</div>
            <div><span className="font-semibold">$100K+</span> combined purchase value</div>
            <div><span className="font-semibold">$300M &ndash; $5B</span> market capitalisation</div>
            <div><span className="font-semibold">Within 60 days</span> of the next earnings date</div>
          </div>
        </div>

        <p className="text-sm text-gray-600 leading-relaxed">
          Returns are measured from the <span className="font-semibold">filing date</span>, not the
          transaction date &mdash; the first price an investor could actually have paid. Every signal
          traces back to a public filing, and the signals we <span className="font-semibold">reject</span>{' '}
          are published too, with the reasoning: see the{' '}
          <Link to="/research-queue" className="text-blue-700 font-medium hover:text-blue-800">
            research queue
          </Link>
          .
        </p>

        {/* We trade our own signals. Claim EXECUTABILITY, not outperformance — the
            portfolio is small and currently negative, and the page shows that. Anyone
            who clicks through sees the real numbers, so the copy must not contradict
            what they will find. */}
        <p className="mt-3 text-sm text-gray-600 leading-relaxed">
          We also <span className="font-semibold">trade these signals ourselves</span> in a
          paper account: entries and exits are pre-registered, and every fill is recorded
          against the signal&rsquo;s day-zero price so implementation shortfall is measured
          rather than assumed. Positions, fills and the equity curve against SPY are all
          public &mdash; see the{' '}
          <Link to="/portfolio" className="text-blue-700 font-medium hover:text-blue-800">
            portfolio
          </Link>
          , or{' '}
          <Link to="/performance" className="text-blue-700 font-medium hover:text-blue-800">
            track every signal &rarr;
          </Link>
        </p>
      </div>

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
                      {highConv && (
                        <span className="bg-green-50 text-green-800 px-2 py-0.5 rounded text-xs font-bold uppercase">
                          High Conviction
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
