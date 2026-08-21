import { useEffect, useState, useMemo } from 'react'
import { nearMissApi, NearMiss as NearMissItem } from '../services/api'

type SortKey = 'pct_of_mcap' | 'total_value' | 'insider_count' | 'ticker' | 'window_end'
type SortDir = 'asc' | 'desc'

const VERDICT_STYLES: Record<string, string> = {
  watch: 'bg-amber-100 text-amber-900',
  pass: 'bg-gray-100 text-gray-600',
  blocklist_candidate: 'bg-red-100 text-red-900',
}

function fmtMoney(value: number) {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`
  if (value >= 1_000) return `$${Math.round(value / 1_000)}K`
  return `$${Math.round(value)}`
}

export default function NearMiss() {
  const [items, setItems] = useState<NearMissItem[]>([])
  const [caveat, setCaveat] = useState('')
  const [sinceDate, setSinceDate] = useState('')
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(60)
  const [sortKey, setSortKey] = useState<SortKey>('pct_of_mcap')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false
    setLoading(true)
    nearMissApi.getQueue(days)
      .then((res) => {
        if (ignore) return
        setItems(res.data?.near_misses || [])
        setCaveat(res.data?.caveat || '')
        setSinceDate(res.data?.since_date || '')
      })
      .catch(() => { if (!ignore) setItems([]) })
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [days])

  const sorted = useMemo(() => {
    return [...items].sort((a, b) => {
      let av: number | string = 0, bv: number | string = 0
      if (sortKey === 'ticker') { av = a.ticker || ''; bv = b.ticker || '' }
      else if (sortKey === 'window_end') { av = a.window_end || ''; bv = b.window_end || '' }
      else { av = a[sortKey] ?? 0; bv = b[sortKey] ?? 0 }
      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [items, sortKey, sortDir])

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(key); setSortDir('desc') }
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return ''
    return sortDir === 'asc' ? ' ↑' : ' ↓'
  }

  const totalValue = items.reduce((sum, n) => sum + (n.total_value || 0), 0)
  const reviewed = items.filter(n => n.research_notes.length > 0).length

  return (
    <div>
      {/* Framing — these are not signals. Rendered with the data, never separated from it. */}
      <div className="border-l-4 border-amber-500 bg-amber-50 px-4 py-3 mb-6">
        <div className="text-xs font-semibold uppercase tracking-wider text-amber-900">
          Research Queue · Filtered — Earnings Timing
        </div>
        <p className="text-sm text-amber-900/90 mt-1">{caveat}</p>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center justify-between gap-y-3 gap-x-4 mb-6">
        <div className="flex flex-wrap items-center gap-2">
          {[30, 60, 90, 180].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                days === d ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              Last {d}d
            </button>
          ))}
        </div>
        {sinceDate && (
          <span className="text-sm text-gray-500 whitespace-nowrap">Since {sinceDate}</span>
        )}
      </div>

      {/* Header stats */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3 md:flex md:gap-10 mb-6 pb-6 border-b border-gray-200">
        <div>
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Companies</div>
          <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">{items.length}</div>
        </div>
        <div>
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Insider Buying</div>
          <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">{fmtMoney(totalValue)}</div>
        </div>
        <div>
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Researched</div>
          <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            {reviewed}<span className="text-gray-300 text-xl"> / {items.length}</span>
          </div>
        </div>
      </div>

      {/* Queue table */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Loading...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          No earnings-filtered clusters in this window.
        </div>
      ) : (
        <div className="border-t-2 border-gray-900 overflow-x-auto">
          <div className="grid grid-cols-[70px_1fr_70px_90px_90px_90px_130px_90px] gap-x-2 text-xs text-gray-600 uppercase tracking-wider py-2.5 border-b border-gray-200 min-w-[820px]">
            <span className="cursor-pointer hover:text-gray-900" onClick={() => toggleSort('ticker')}>
              Ticker{sortIndicator('ticker')}
            </span>
            <span>Company</span>
            <span className="text-right cursor-pointer hover:text-gray-900" onClick={() => toggleSort('insider_count')}>
              Buyers{sortIndicator('insider_count')}
            </span>
            <span className="text-right cursor-pointer hover:text-gray-900" onClick={() => toggleSort('total_value')}>
              Bought{sortIndicator('total_value')}
            </span>
            <span className="text-right">Mkt Cap</span>
            <span className="text-right cursor-pointer hover:text-gray-900" onClick={() => toggleSort('pct_of_mcap')}>
              % of Cap{sortIndicator('pct_of_mcap')}
            </span>
            <span className="cursor-pointer hover:text-gray-900" onClick={() => toggleSort('window_end')}>
              Window{sortIndicator('window_end')}
            </span>
            <span>Verdict</span>
          </div>

          {sorted.map((n) => {
            const isOpen = expanded === n.cik
            const note = n.research_notes[0]
            return (
              <div key={n.cik} className="border-b border-gray-100 min-w-[820px]">
                <div
                  onClick={() => setExpanded(isOpen ? null : n.cik)}
                  className="grid grid-cols-[70px_1fr_70px_90px_90px_90px_130px_90px] gap-x-2 py-3 text-sm items-center cursor-pointer hover:bg-gray-50"
                >
                  <span className="font-bold">{n.ticker}</span>
                  <span className="text-gray-600 truncate pr-2">{n.company_name}</span>
                  <span className="text-right tabular-nums">{n.insider_count}</span>
                  <span className="text-right tabular-nums">{fmtMoney(n.total_value)}</span>
                  <span className="text-right tabular-nums text-gray-500">{fmtMoney(n.market_cap)}</span>
                  <span className="text-right tabular-nums font-semibold">{n.pct_of_mcap.toFixed(2)}%</span>
                  <span className="text-gray-500 text-xs tabular-nums">
                    {n.window_start} → {n.window_end}
                  </span>
                  <span>
                    {n.verdict ? (
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${VERDICT_STYLES[n.verdict] || 'bg-gray-100 text-gray-600'}`}>
                        {n.verdict.split('_').join(' ')}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">unreviewed</span>
                    )}
                  </span>
                </div>

                {isOpen && (
                  <div className="bg-gray-50 px-4 py-4 text-sm">
                    <div className="text-xs text-gray-600 uppercase tracking-wider mb-2">Buyers</div>
                    <div className="space-y-1 mb-4">
                      {n.buyers.map((b) => (
                        <div key={`${b.insider_name}-${b.transaction_date}`} className="flex flex-wrap gap-x-3">
                          <span className="font-medium">{b.insider_name}</span>
                          <span className="text-gray-500">{b.insider_title || b.role}</span>
                          <span className="text-gray-500 tabular-nums">{b.transaction_date}</span>
                          <span className="tabular-nums">{fmtMoney(b.value)}</span>
                          {b.form4_url && (
                            <a
                              href={b.form4_url}
                              target="_blank"
                              rel="noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-blue-700 hover:text-blue-800"
                            >
                              Form 4 ↗
                            </a>
                          )}
                        </div>
                      ))}
                    </div>

                    {n.filter_reason && (
                      <div className="mb-4">
                        <div className="text-xs text-gray-600 uppercase tracking-wider mb-1">Why it was filtered</div>
                        <div className="text-gray-700">{n.filter_reason}</div>
                      </div>
                    )}

                    {note ? (
                      <div>
                        <div className="text-xs text-gray-600 uppercase tracking-wider mb-1">
                          Research note · {note.note_date}
                        </div>
                        <div className="text-gray-700">{note.thesis}</div>
                        {note.risk_flags.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {note.risk_flags.map((f) => (
                              <span key={f} className="px-2 py-0.5 rounded bg-red-50 text-red-800 text-xs">
                                {f.split('_').join(' ')}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-gray-400 text-xs">No research note recorded.</div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
