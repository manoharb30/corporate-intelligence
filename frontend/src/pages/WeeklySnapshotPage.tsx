import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { snapshotApi, WeekSnapshotData } from '../services/api'

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`
  return `$${v.toFixed(0)}`
}

function eventLabel(t: string): string {
  const map: Record<string, string> = {
    material_agreement: 'Material Agreement',
    executive_change: 'Exec Change',
    governance_change: 'Governance',
    acquisition_disposition: 'Acquisition',
    rights_modification: 'Rights Mod',
  }
  return map[t] || t
}

function eventPillColor(t: string): string {
  const map: Record<string, string> = {
    material_agreement: 'bg-amber-100 text-amber-700',
    executive_change: 'bg-blue-100 text-blue-700',
    governance_change: 'bg-purple-100 text-purple-700',
    acquisition_disposition: 'bg-green-100 text-green-700',
    rights_modification: 'bg-pink-100 text-pink-700',
  }
  return map[t] || 'bg-gray-100 text-gray-600'
}

export default function WeeklySnapshotPage() {
  const [data, setData] = useState<WeekSnapshotData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false
    snapshotApi.getWeekSnapshot('2026-03-03', '2026-03-07')
      .then(res => { if (!ignore) setData(res.data) })
      .catch(err => { if (!ignore) setError(err.message || 'Failed to load') })
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full"></div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center">
        <p className="text-red-600 text-lg">Failed to load snapshot data</p>
        <p className="text-gray-500 text-sm mt-2">{error}</p>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto py-10">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
          Weekly Snapshot: Mar 3-7, 2026
        </h1>
        <p className="text-gray-500 mt-2 max-w-2xl">
          What our system detected — click any ticker to see what happened since.
        </p>
      </div>

      {/* ===== Section A: Insider Cluster Signals ===== */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-1.5 h-8 bg-green-500 rounded-full"></div>
          <h2 className="text-xl font-bold text-gray-900">Insider Cluster Signals</h2>
          <span className="text-xs text-gray-400">{data.clusters.length} signals</span>
        </div>
        <p className="text-sm text-gray-500 ml-5 mb-5">
          Coordinated insider buying and selling detected during the week
        </p>

        {data.clusters.length > 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Company</th>
                  <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                  <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</th>
                  <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">What We Detected</th>
                  <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Value</th>
                </tr>
              </thead>
              <tbody>
                {data.clusters.map((c, idx) => {
                  const isBuy = c.direction === 'buy'
                  const pillColor = isBuy
                    ? (c.signal_level === 'high' ? 'bg-green-100 text-green-700' : 'bg-green-50 text-green-600')
                    : (c.signal_level === 'high' ? 'bg-red-100 text-red-700' : 'bg-red-50 text-red-600')
                  const pillLabel = isBuy ? 'Cluster Buy' : 'Cluster Sell'
                  const levelBadge = c.signal_level === 'high'
                    ? 'border-l-4 border-l-green-500'
                    : ''

                  return (
                    <tr
                      key={`cluster-${c.cik}-${idx}`}
                      className={`border-b border-gray-50 hover:bg-gray-50 transition-colors ${levelBadge}`}
                    >
                      <td className="px-4 py-3">
                        <Link
                          to={`/signal/${encodeURIComponent(c.accession_number)}`}
                          className="group"
                        >
                          <span className="font-bold text-gray-900 group-hover:text-primary-600">{c.ticker || '—'}</span>
                          <span className="text-gray-500 text-xs ml-2 truncate">{c.company_name}</span>
                        </Link>
                      </td>
                      <td className="px-3 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-bold ${pillColor}`}>
                          {pillLabel}
                        </span>
                        {c.signal_level === 'high' && (
                          <span className="ml-1.5 text-[10px] font-bold text-amber-600 uppercase">HIGH</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-gray-600 whitespace-nowrap text-xs">
                        {c.signal_date}
                      </td>
                      <td className="px-3 py-3 text-gray-700 text-xs">
                        {c.description}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-xs whitespace-nowrap">
                        <span className={isBuy ? 'text-green-700' : 'text-red-700'}>
                          {formatVolume(c.total_value)}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-6 text-center bg-white rounded-xl border border-gray-200">
            No insider clusters detected for this week
          </p>
        )}
      </section>

      {/* ===== Section B: Pre-Event Insider Activity ===== */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-1.5 h-8 bg-purple-500 rounded-full"></div>
          <h2 className="text-xl font-bold text-gray-900">Pre-Event Insider Activity</h2>
          <span className="text-xs text-gray-400">{data.anomalies.length} events</span>
        </div>
        <p className="text-sm text-gray-500 ml-5 mb-5">
          8-K filings from this week where insiders sold shares before the public announcement
        </p>

        {data.anomalies.length > 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-purple-50/50">
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Company</th>
                  <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Event</th>
                  <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Date</th>
                  <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">What We Detected</th>
                  <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide">Pre-Event Selling</th>
                </tr>
              </thead>
              <tbody>
                {data.anomalies.map((a, idx) => (
                  <tr
                    key={`anomaly-${a.cik}-${idx}`}
                    className="border-b border-gray-50 hover:bg-purple-50/30 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Link
                        to={`/signal/${encodeURIComponent(a.accession_number)}`}
                        className="group"
                      >
                        <span className="font-bold text-gray-900 group-hover:text-primary-600">{a.ticker || '—'}</span>
                        <span className="text-gray-500 text-xs ml-2 truncate">{a.company_name}</span>
                      </Link>
                    </td>
                    <td className="px-3 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${eventPillColor(a.event_type)}`}>
                        {eventLabel(a.event_type)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-gray-600 whitespace-nowrap text-xs">
                      {a.event_date}
                    </td>
                    <td className="px-3 py-3 text-gray-700 text-xs">
                      {a.description}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-red-600 text-xs whitespace-nowrap">
                      {formatVolume(a.pre_sell_value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-6 text-center bg-white rounded-xl border border-gray-200">
            No pre-event anomalies detected for this week
          </p>
        )}
      </section>

      {/* Footer note */}
      <div className="text-center text-xs text-gray-400 py-6 border-t border-gray-100">
        Data sourced from SEC EDGAR Form 4 and 8-K filings. Prices available on individual signal pages.
      </div>
    </div>
  )
}
