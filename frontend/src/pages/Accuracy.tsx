import { useState, useEffect } from 'react'
import { accuracyApi, type AccuracyResponse, type SignalOutcome, type LevelStats } from '../services/api'

const VERDICT_COLORS: Record<string, { bg: string; text: string }> = {
  hit: { bg: 'bg-green-100', text: 'text-green-800' },
  partial_hit: { bg: 'bg-yellow-100', text: 'text-yellow-800' },
  miss: { bg: 'bg-red-100', text: 'text-red-800' },
  pending: { bg: 'bg-gray-100', text: 'text-gray-600' },
  no_data: { bg: 'bg-gray-50', text: 'text-gray-400' },
}

const LEVEL_COLORS: Record<string, string> = {
  high: 'border-red-500 bg-red-50',
  medium: 'border-yellow-500 bg-yellow-50',
  low: 'border-blue-500 bg-blue-50',
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const colors = VERDICT_COLORS[verdict] || VERDICT_COLORS.no_data
  const label = verdict === 'partial_hit' ? 'Partial' : verdict === 'no_data' ? 'No Data' : verdict.charAt(0).toUpperCase() + verdict.slice(1)
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors.bg} ${colors.text}`}>
      {label}
    </span>
  )
}

function PctCell({ value }: { value: number | null }) {
  if (value === null) return <span className="text-gray-400">--</span>
  const color = value >= 10 ? 'text-green-600 font-semibold' : value >= 0 ? 'text-yellow-600' : 'text-red-600'
  return <span className={color}>{value > 0 ? '+' : ''}{value.toFixed(1)}%</span>
}

function StatCard({ label, value, subtitle }: { label: string; value: string; subtitle?: string }) {
  return (
    <div className="bg-white rounded-lg shadow p-5">
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
      {subtitle && <p className="mt-1 text-xs text-gray-400">{subtitle}</p>}
    </div>
  )
}

function LevelCard({ stats }: { stats: LevelStats }) {
  const colors = LEVEL_COLORS[stats.level] || 'border-gray-300 bg-gray-50'
  return (
    <div className={`rounded-lg border-l-4 p-4 ${colors}`}>
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-700">
        {stats.level} signals
      </h3>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <span className="text-gray-500">Count:</span>{' '}
          <span className="font-medium">{stats.count}</span>
        </div>
        <div>
          <span className="text-gray-500">Scoreable:</span>{' '}
          <span className="font-medium">{stats.scoreable}</span>
        </div>
        <div>
          <span className="text-gray-500">Hit Rate:</span>{' '}
          <span className="font-semibold">
            {stats.hit_rate !== null ? `${stats.hit_rate}%` : '--'}
          </span>
        </div>
        <div>
          <span className="text-gray-500">8-K Follow:</span>{' '}
          <span className="font-medium">
            {stats.eight_k_follow_rate !== null ? `${stats.eight_k_follow_rate}%` : '--'}
          </span>
        </div>
        <div>
          <span className="text-gray-500">Avg 30d:</span>{' '}
          <PctCell value={stats.avg_return_30d} />
        </div>
        <div>
          <span className="text-gray-500">Avg 60d:</span>{' '}
          <PctCell value={stats.avg_return_60d} />
        </div>
        <div className="col-span-2">
          <span className="text-gray-500">Avg 90d:</span>{' '}
          <PctCell value={stats.avg_return_90d} />
        </div>
      </div>
      <div className="mt-3 flex gap-2 text-xs">
        <span className="text-green-700">{stats.hits} hits</span>
        <span className="text-yellow-700">{stats.partial_hits} partial</span>
        <span className="text-red-700">{stats.misses} misses</span>
      </div>
    </div>
  )
}

export default function Accuracy() {
  const [data, setData] = useState<AccuracyResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lookbackDays, setLookbackDays] = useState(365)
  const [minLevel, setMinLevel] = useState('medium')

  useEffect(() => {
    setLoading(true)
    setError(null)
    accuracyApi
      .getAccuracy(lookbackDays, 30, minLevel)
      .then((res) => setData(res.data))
      .catch((err) => setError(err?.response?.data?.detail || 'Failed to load accuracy data'))
      .finally(() => setLoading(false))
  }, [lookbackDays, minLevel])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600 mx-auto" />
          <p className="mt-4 text-gray-500">Computing signal accuracy...</p>
          <p className="mt-1 text-xs text-gray-400">Fetching price data for all tracked signals</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 p-6 text-center">
        <p className="text-red-800 font-medium">Error loading accuracy data</p>
        <p className="mt-1 text-red-600 text-sm">{error}</p>
      </div>
    )
  }

  if (!data) return null

  const { summary, signals } = data

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Signal Accuracy Tracker</h1>
          <p className="mt-1 text-sm text-gray-500">
            How insider cluster signals performed — price action and subsequent 8-K events
          </p>
        </div>
        <div className="flex gap-3">
          <select
            value={lookbackDays}
            onChange={(e) => setLookbackDays(Number(e.target.value))}
            className="rounded-md border-gray-300 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
          >
            <option value={90}>Last 90 days</option>
            <option value={180}>Last 180 days</option>
            <option value={365}>Last 365 days</option>
          </select>
          <select
            value={minLevel}
            onChange={(e) => setMinLevel(e.target.value)}
            className="rounded-md border-gray-300 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
          >
            <option value="high">HIGH only</option>
            <option value="medium">MEDIUM+</option>
            <option value="low">All levels</option>
          </select>
        </div>
      </div>

      {/* Summary stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Overall Hit Rate"
          value={summary.overall_hit_rate !== null ? `${summary.overall_hit_rate}%` : '--'}
          subtitle={`${summary.scoreable_signals} scoreable of ${summary.total_signals} total`}
        />
        <StatCard
          label="Avg 90d Return"
          value={summary.overall_avg_return_90d !== null ? `${summary.overall_avg_return_90d > 0 ? '+' : ''}${summary.overall_avg_return_90d}%` : '--'}
          subtitle="Mean return at 90 days"
        />
        <StatCard
          label="8-K Follow Rate"
          value={summary.overall_8k_follow_rate !== null ? `${summary.overall_8k_follow_rate}%` : '--'}
          subtitle="Signals followed by material event"
        />
        <StatCard
          label="Signals Tracked"
          value={String(summary.total_signals)}
          subtitle={`${lookbackDays}d lookback`}
        />
      </div>

      {/* 8-K Follow Rate Breakdown */}
      {(() => {
        const withEightK = signals.filter((s) => s.followed_by_8k).length
        const pending = signals.filter((s) => s.signal_age_days < 30).length
        const noData = signals.filter((s) => s.verdict === 'no_data').length
        const mature = summary.total_signals - pending - noData
        const matureRate = mature > 0 ? ((withEightK / mature) * 100).toFixed(1) : null

        return (
          <div className="bg-white rounded-lg shadow p-5">
            <h2 className="text-lg font-semibold text-gray-800 mb-1">8-K Follow Rate Breakdown</h2>
            <p className="text-sm text-gray-500 mb-4">
              Why {summary.overall_8k_follow_rate ?? '--'}% of signals show a subsequent material 8-K event
            </p>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 pr-4 font-medium text-gray-600">Category</th>
                    <th className="text-right py-2 px-4 font-medium text-gray-600">Signals</th>
                    <th className="text-right py-2 px-4 font-medium text-gray-600">% of Total</th>
                    <th className="text-left py-2 pl-4 font-medium text-gray-600">Explanation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  <tr>
                    <td className="py-2.5 pr-4 font-medium text-green-700">8-K filed after signal</td>
                    <td className="py-2.5 px-4 text-right font-semibold">{withEightK}</td>
                    <td className="py-2.5 px-4 text-right">{((withEightK / summary.total_signals) * 100).toFixed(1)}%</td>
                    <td className="py-2.5 pl-4 text-gray-500">Material event confirmed after cluster detection</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 pr-4 font-medium text-gray-500">Signal too recent (&lt;30d)</td>
                    <td className="py-2.5 px-4 text-right font-semibold">{pending}</td>
                    <td className="py-2.5 px-4 text-right">{((pending / summary.total_signals) * 100).toFixed(1)}%</td>
                    <td className="py-2.5 pl-4 text-gray-500">Not enough time elapsed — still in prediction window</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 pr-4 font-medium text-gray-400">No price/event data</td>
                    <td className="py-2.5 px-4 text-right font-semibold">{noData}</td>
                    <td className="py-2.5 px-4 text-right">{((noData / summary.total_signals) * 100).toFixed(1)}%</td>
                    <td className="py-2.5 pl-4 text-gray-500">Company not yet scanned for 8-K filings</td>
                  </tr>
                  <tr>
                    <td className="py-2.5 pr-4 font-medium text-yellow-700">Mature, no 8-K yet</td>
                    <td className="py-2.5 px-4 text-right font-semibold">{mature - withEightK}</td>
                    <td className="py-2.5 px-4 text-right">{(((mature - withEightK) / summary.total_signals) * 100).toFixed(1)}%</td>
                    <td className="py-2.5 pl-4 text-gray-500">Signal old enough but no material event filed yet</td>
                  </tr>
                </tbody>
              </table>
            </div>
            {matureRate && (
              <p className="mt-4 text-sm text-gray-600">
                Among <span className="font-semibold">{mature} mature signals</span> (30+ days old, with data),{' '}
                <span className="font-semibold text-green-700">{matureRate}%</span> were followed by a material 8-K event.
              </p>
            )}
          </div>
        )
      })()}

      {/* Level comparison */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">By Signal Level</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {(['high', 'medium', 'low'] as const).map((level) => {
            const stats = summary.by_level[level]
            return stats ? <LevelCard key={level} stats={stats} /> : null
          })}
        </div>
      </div>

      {/* Signal outcomes table */}
      <div>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          Individual Signals ({signals.length})
        </h2>
        <div className="overflow-x-auto bg-white rounded-lg shadow">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ticker</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Level</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Age</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">30d</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">60d</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">90d</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">8-K</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Verdict</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {signals.map((s: SignalOutcome, i: number) => (
                <tr key={`${s.cik}-${s.signal_date}-${i}`} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">
                    <a
                      href={`/signal/CLUSTER-${s.cik}-${s.signal_date}`}
                      className="text-primary-600 hover:underline font-medium"
                    >
                      {s.company_name.length > 30
                        ? s.company_name.slice(0, 28) + '...'
                        : s.company_name}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{s.ticker || '--'}</td>
                  <td className="px-4 py-3 text-sm">
                    <span
                      className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                        s.signal_level === 'high'
                          ? 'bg-red-100 text-red-700'
                          : s.signal_level === 'medium'
                          ? 'bg-yellow-100 text-yellow-700'
                          : 'bg-blue-100 text-blue-700'
                      }`}
                    >
                      {s.signal_level.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{s.signal_date}</td>
                  <td className="px-4 py-3 text-sm text-right text-gray-500">{s.signal_age_days}d</td>
                  <td className="px-4 py-3 text-sm text-right"><PctCell value={s.price_change_30d} /></td>
                  <td className="px-4 py-3 text-sm text-right"><PctCell value={s.price_change_60d} /></td>
                  <td className="px-4 py-3 text-sm text-right"><PctCell value={s.price_change_90d} /></td>
                  <td className="px-4 py-3 text-sm text-center">
                    {s.followed_by_8k ? (
                      <span className="text-green-600 font-medium" title={`${s.days_to_first_8k}d to first 8-K`}>
                        Yes{s.days_to_first_8k !== null ? ` (${s.days_to_first_8k}d)` : ''}
                      </span>
                    ) : (
                      <span className="text-gray-400">No</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-center">
                    <VerdictBadge verdict={s.verdict} />
                  </td>
                </tr>
              ))}
              {signals.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-gray-500">
                    No signals found for the selected filters
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
