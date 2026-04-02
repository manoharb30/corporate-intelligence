/**
 * SignalContext — "Signal Context" card.
 *
 * Pulls surrounding graph context for a signal: recent events, activist filings,
 * insider track record, opposing activity, prior alerts, and volume summary.
 */

import { useEffect, useState } from 'react'
import { signalContextApi, SignalContextData } from '../services/api'

interface SignalContextProps {
  cik: string
  signalDate: string
  direction: 'buy' | 'sell'
  insiderNames?: string[]
}

function formatValue(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`
  return `$${v.toLocaleString()}`
}

export default function SignalContext({ cik, signalDate, direction, insiderNames = [] }: SignalContextProps) {
  const [data, setData] = useState<SignalContextData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let ignore = false
    signalContextApi.get(cik, signalDate, direction, insiderNames)
      .then(res => { if (!ignore) setData(res.data) })
      .catch(() => {})
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [cik, signalDate, direction])

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <svg className="w-4 h-4 text-gray-400 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm text-gray-400">Loading context...</span>
        </div>
      </div>
    )
  }

  if (!data) return null

  // Build bullet points — only for non-empty results
  const bullets: Array<{ text: string; color?: string }> = []

  // Recent events
  const maEvents = (data.recent_events || []).filter(e => e.is_ma)
  if (maEvents.length > 0) {
    for (const e of maEvents.slice(0, 3)) {
      bullets.push({ text: `${e.type} filed on ${e.date}` })
    }
  }

  // Activist filings
  for (const a of (data.activist_filings || []).slice(0, 2)) {
    const pct = a.percentage ? ` with ${a.percentage}% stake` : ''
    bullets.push({ text: `${a.filer} filed ${a.form_type || '13D'}${pct} on ${a.date}` })
  }

  // Insider history
  for (const h of data.insider_history || []) {
    if (h.prior_trades === 0) {
      bullets.push({ text: `${h.name} is a first-time ${direction === 'buy' ? 'buyer' : 'seller'} at this company` })
    } else {
      const buyStr = h.buys > 0 ? `${h.buys} buy${h.buys !== 1 ? 's' : ''}` : ''
      const sellStr = h.sells > 0 ? `${h.sells} sell${h.sells !== 1 ? 's' : ''}` : ''
      const parts = [buyStr, sellStr].filter(Boolean).join(', ')
      bullets.push({ text: `${h.name} has ${h.prior_trades} prior trade${h.prior_trades !== 1 ? 's' : ''} here (${parts})` })
    }
  }

  // Opposing activity
  const opp = data.opposing_activity || []
  if (opp.length === 0) {
    const oppLabel = direction === 'buy' ? 'selling' : 'buying'
    bullets.push({ text: `No insiders are ${oppLabel} — pure ${direction} conviction`, color: 'text-green-600' })
  } else {
    const oppAction = direction === 'buy' ? 'sold' : 'bought'
    for (const o of opp.slice(0, 3)) {
      const val = o.value ? ` ${formatValue(o.value)}` : ''
      const title = o.title ? ` (${o.title})` : ''
      bullets.push({
        text: `${o.name}${title} ${oppAction}${val} on ${o.date} while other insiders are ${direction === 'buy' ? 'buying' : 'selling'}`,
        color: 'text-amber-600',
      })
    }
  }

  // Prior alerts
  const alerts = data.prior_alerts || []
  if (alerts.length === 0) {
    bullets.push({ text: 'First signal we\'ve detected for this company' })
  } else {
    const a = alerts[0]
    const label = a.type === 'insider_cluster' ? 'buy cluster' :
                  a.type === 'insider_sell_cluster' ? 'sell cluster' :
                  a.type === 'activist_filing' ? 'activist filing' : a.type
    bullets.push({ text: `Previous alert on ${a.date}: ${a.severity} ${label}` })
    if (alerts.length > 1) {
      bullets.push({ text: `${alerts.length} total prior alerts for this company` })
    }
  }

  // Volume summary
  if (data.volume && data.volume.total_txns > 0) {
    const v = data.volume
    const dominant = v.total_buying > v.total_selling * 1.5 ? 'net buying' :
                     v.total_selling > v.total_buying * 1.5 ? 'net selling' : 'mixed'
    bullets.push({
      text: `12-month insider activity: ${v.total_txns} trades by ${v.distinct_insiders} insiders (${dominant}). Buying: ${formatValue(v.total_buying)}, Selling: ${formatValue(v.total_selling)}`,
    })
  }

  if (bullets.length === 0) return null

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 mb-4">
      <div className="flex items-center gap-2 mb-1">
        <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <h3 className="text-sm font-bold text-gray-900">Signal Context</h3>
      </div>
      <p className="text-xs text-gray-500 mb-3">What else we know about this company</p>
      <ul className="space-y-2">
        {bullets.map((b, i) => (
          <li key={i} className={`flex items-start gap-2 text-sm leading-relaxed ${b.color || 'text-gray-700'}`}>
            <span className="text-gray-300 mt-1 shrink-0">—</span>
            <span>{b.text}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
