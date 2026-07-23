import { useEffect, useState } from 'react'
import { signalWatchApi, SignalWatchResponse, WatchPromise, WatchEvent } from '../services/api'

// Plain-language labels — never expose node/DB terminology in the UI.
const VERDICT_LABEL: Record<WatchPromise['verdict'], string> = {
  pass: 'Delivered',
  fail: 'Walked back',
  pending: 'Awaiting next report',
}

const VERDICT_STYLE: Record<WatchPromise['verdict'], string> = {
  pass: 'bg-green-50 text-green-800 border-green-200',
  fail: 'bg-red-50 text-red-800 border-red-200',
  pending: 'bg-amber-50 text-amber-800 border-amber-200',
}

const DIRECTION_DOT: Record<WatchEvent['direction'], string> = {
  confirming: 'bg-green-600',
  breaking: 'bg-red-600',
  neutral: 'bg-gray-400',
}

const EVENT_TYPE_LABEL: Record<string, string> = {
  earnings_call: 'Earnings',
  guidance: 'Guidance',
  capital_action: 'Capital action',
  regulatory: 'Regulatory',
  insider_followon: 'Insider activity',
  ma: 'M&A',
  analyst: 'Analyst',
  index: 'Index change',
}

function summaryLine(w: SignalWatchResponse): { text: string; cls: string } {
  const s = w.summary
  if (s.failed > 0) {
    return {
      text: `${s.failed} of ${s.total} promises walked back — thesis under pressure`,
      cls: 'text-red-800',
    }
  }
  if (s.pending === 0 && s.total > 0) {
    return {
      text: `${s.passed} of ${s.total} promises delivered — thesis on track`,
      cls: 'text-green-800',
    }
  }
  return {
    text: `${s.passed} delivered · ${s.pending} awaiting the next report`,
    cls: 'text-gray-700',
  }
}

export default function SignalWatch({ ticker, signalDate }: { ticker: string; signalDate: string }) {
  const [watch, setWatch] = useState<SignalWatchResponse | null>(null)

  useEffect(() => {
    if (!ticker || !signalDate) return
    let ignore = false
    signalWatchApi
      .getWatch(ticker, signalDate.slice(0, 10))
      .then((res) => {
        if (!ignore) setWatch(res.data)
      })
      .catch(() => {
        // 404 = no watch data for this signal; the section simply doesn't render
        if (!ignore) setWatch(null)
      })
    return () => { ignore = true }
  }, [ticker, signalDate])

  if (!watch || (watch.promises.length === 0 && watch.events.length === 0)) return null

  const line = summaryLine(watch)
  const windowEvents = watch.events.filter((e) => e.day_index >= 0 && e.day_index <= 90)

  return (
    <div className="mb-8">
      <h3 className="font-bold text-base mb-1">What Management Promised — and Delivered</h3>
      <div className="text-xs text-gray-500 mb-3">
        Commitments from the last earnings call before the insiders bought, checked against each new report.
      </div>
      <div className={`text-sm font-semibold mb-4 ${line.cls}`}>{line.text}</div>

      {/* Promise checklist */}
      {watch.promises.length > 0 && (
        <div className="border-t-2 border-gray-900 mb-6">
          {watch.promises.map((p, i) => (
            <div key={i} className="py-3 border-b border-gray-100">
              <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                <div className="min-w-0">
                  <span className="font-semibold text-sm">{p.metric}</span>
                  {p.target && <span className="text-sm text-gray-500 ml-2">promised: {p.target}</span>}
                </div>
                <span className={`flex-shrink-0 border px-2 py-0.5 rounded text-xs font-semibold ${VERDICT_STYLE[p.verdict]}`}>
                  {p.verdict === 'pass' ? '✓ ' : p.verdict === 'fail' ? '✗ ' : ''}
                  {VERDICT_LABEL[p.verdict]}
                </span>
              </div>
              {p.quote && (
                <div className="text-sm text-gray-500 italic mt-1">“{p.quote}”</div>
              )}
              {(p.source_call_date || p.source_url) && (
                <div className="text-xs text-gray-400 mt-0.5">
                  {p.source_url ? (
                    <a
                      href={p.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-700 font-medium hover:text-blue-800"
                    >
                      {p.source_call_date ? `${p.source_call_date} earnings call` : 'Source'} →
                    </a>
                  ) : (
                    <span>{p.source_call_date} earnings call</span>
                  )}
                </div>
              )}
              {p.actual && (
                <div className="text-sm text-gray-600 mt-1">
                  <span className="text-gray-400">Actual:</span> {p.actual}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 90-day window track */}
      {windowEvents.length > 0 && (
        <>
          <div className="text-xs text-gray-600 uppercase tracking-wider font-semibold mb-2">
            Since the insiders bought
          </div>
          <div className="relative h-6 mb-1">
            <div className="absolute left-0 right-0 top-2.5 h-0.5 bg-gray-200 rounded" />
            {windowEvents.map((e, i) => (
              <span
                key={i}
                title={`Day ${e.day_index}: ${e.headline}`}
                className={`absolute top-1 w-3 h-3 rounded-full border-2 border-white ${DIRECTION_DOT[e.direction]}`}
                style={{ left: `calc(${Math.min(e.day_index, 90) / 0.9}% - 6px)` }}
              />
            ))}
          </div>
          <div className="flex justify-between text-xs text-gray-400 mb-3">
            <span>Day 0 · insiders bought</span>
            <span>Day 90 · window closes</span>
          </div>

          {/* Event list */}
          <div className="space-y-3">
            {watch.events.map((e, i) => (
              <div key={i} className="flex gap-3 text-sm">
                <span className={`mt-1.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${DIRECTION_DOT[e.direction]}`} />
                <div className="min-w-0">
                  <div>
                    <span className="text-gray-500">
                      Day {e.day_index} · {e.event_date} · {EVENT_TYPE_LABEL[e.event_type] || e.event_type}
                    </span>
                  </div>
                  <div className="font-semibold">{e.headline}</div>
                  {e.detail && <div className="text-gray-600 text-sm mt-0.5">{e.detail}</div>}
                  {e.source_url && (
                    <a
                      href={e.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-700 text-xs font-medium hover:text-blue-800"
                    >
                      Source →
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
