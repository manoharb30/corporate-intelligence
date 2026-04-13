import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { signalReturnsApi, SignalReturnRow, SignalReturnsSummary } from '../services/api'

type FilterTab = 'all' | 'buy' | 'sell' | 'profit'
type SortKey = 'signal_date' | 'return_pct' | 'total_value' | 'ticker'

function formatMoney(v: number | null | undefined): string {
  if (v == null) return '-'
  const abs = Math.abs(v)
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
  if (abs >= 1e3) return `$${(v / 1e3).toFixed(0)}K`
  return `$${v.toFixed(0)}`
}

function formatPct(v: number | null | undefined): string {
  if (v == null) return '-'
  const sign = v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(1)}%`
}

function colorClass(v: number | null | undefined, direction: 'buy' | 'sell'): string {
  if (v == null) return 'text-gray-400'
  if (direction === 'buy') return v >= 0 ? 'text-green-600' : 'text-red-600'
  return v <= 0 ? 'text-green-600' : 'text-red-600'
}

const MONTHS = [
  { value: 0, label: 'All months' },
  { value: 1, label: 'Jan' }, { value: 2, label: 'Feb' }, { value: 3, label: 'Mar' },
  { value: 4, label: 'Apr' }, { value: 5, label: 'May' }, { value: 6, label: 'Jun' },
  { value: 7, label: 'Jul' }, { value: 8, label: 'Aug' }, { value: 9, label: 'Sep' },
  { value: 10, label: 'Oct' }, { value: 11, label: 'Nov' }, { value: 12, label: 'Dec' },
]

const YEARS = [0, 2026, 2025, 2024]

export default function Performance() {
  const [signals, setSignals] = useState<SignalReturnRow[]>([])
  const [summary, setSummary] = useState<SignalReturnsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<FilterTab>('all')
  const [year, setYear] = useState<number>(0)
  const [month, setMonth] = useState<number>(0)
  const [sortKey, setSortKey] = useState<SortKey>('signal_date')
  const [sortAsc, setSortAsc] = useState(false)

  useEffect(() => {
    let ignore = false
    setLoading(true)

    const params: { year?: number; month?: number } = {}
    if (year > 0) params.year = year
    if (month > 0 && year > 0) params.month = month

    Promise.all([
      signalReturnsApi.getAll({ ...params, limit: 5000 }),
      signalReturnsApi.getSummary(params),
    ])
      .then(([sigRes, sumRes]) => {
        if (ignore) return
        setSignals(sigRes.data.signals)
        setSummary(sumRes.data)
      })
      .catch(() => {
        if (ignore) return
        setSignals([])
        setSummary(null)
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })

    return () => { ignore = true }
  }, [year, month])

  const filtered = useMemo(() => {
    let list = signals
    if (tab === 'buy') list = list.filter(s => s.direction === 'buy')
    else if (tab === 'sell') list = list.filter(s => s.direction === 'sell')
    else if (tab === 'profit') list = list.filter(s => s.in_profit)

    list = [...list].sort((a, b) => {
      let av: number | string, bv: number | string
      switch (sortKey) {
        case 'return_pct': av = a.return_pct; bv = b.return_pct; break
        case 'total_value': av = a.total_value; bv = b.total_value; break
        case 'ticker': av = a.ticker; bv = b.ticker; break
        default: av = a.signal_date; bv = b.signal_date
      }
      if (av < bv) return sortAsc ? -1 : 1
      if (av > bv) return sortAsc ? 1 : -1
      return 0
    })
    return list
  }, [signals, tab, sortKey, sortAsc])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc)
    else { setSortKey(key); setSortAsc(false) }
  }

  const sortIcon = (key: SortKey) => sortKey !== key ? '' : sortAsc ? ' ↑' : ' ↓'

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">Signal Performance</h1>
        <p className="text-sm text-gray-500 mt-1">
          Live returns for every signal — entry price at signal date, current price today.
        </p>
      </div>


      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {(['all', 'sell', 'buy', 'profit'] as FilterTab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {t === 'all' ? 'All signals' : t === 'sell' ? 'Sell clusters' : t === 'buy' ? 'Buy clusters' : 'In profit'}
            </button>
          ))}
        </div>

        <div className="flex gap-2 ml-auto">
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="px-3 py-1.5 border border-gray-300 rounded-md text-xs bg-white"
          >
            {YEARS.map(y => (
              <option key={y} value={y}>{y === 0 ? 'All years' : y}</option>
            ))}
          </select>
          {year > 0 && (
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="px-3 py-1.5 border border-gray-300 rounded-md text-xs bg-white"
            >
              {MONTHS.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400">
          Loading signals...
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400">
          No signals match the filters.
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left cursor-pointer" onClick={() => handleSort('ticker')}>Ticker{sortIcon('ticker')}</th>
                  <th className="px-3 py-3 text-left">Signal</th>
                  <th className="px-3 py-3 text-left cursor-pointer" onClick={() => handleSort('signal_date')}>Date{sortIcon('signal_date')}</th>
                  <th className="px-3 py-3 text-right">Entry</th>
                  <th className="px-3 py-3 text-right">Current</th>
                  <th className="px-3 py-3 text-right">Today</th>
                  <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort('return_pct')}>Since Signal{sortIcon('return_pct')}</th>
                  <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort('total_value')}>Cluster{sortIcon('total_value')}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, 500).map(s => (
                  <tr key={s.signal_id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link to={`/company/${s.cik}`} className="font-bold text-gray-900 hover:text-blue-600">
                        {s.ticker}
                      </Link>
                      <div className="text-xs text-gray-500 truncate max-w-[200px]">{s.company_name}</div>
                    </td>
                    <td className="px-3 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                        s.direction === 'buy' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
                      }`}>
                        {s.direction === 'buy' ? '▲ Buy' : '▼ Sell'}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-xs font-mono text-gray-500">{s.signal_date}</td>
                    <td className="px-3 py-3 text-right text-xs font-mono text-gray-700">${s.entry_price.toFixed(2)}</td>
                    <td className="px-3 py-3 text-right text-xs font-mono text-gray-900">${s.current_price.toFixed(2)}</td>
                    <td className={`px-3 py-3 text-right text-xs font-mono ${colorClass(s.today_change_pct, 'buy')}`}>
                      {formatPct(s.today_change_pct)}
                    </td>
                    <td className={`px-3 py-3 text-right text-sm font-bold ${colorClass(s.return_pct, s.direction)}`}>
                      {formatPct(s.return_pct)}
                    </td>
                    <td className="px-3 py-3 text-right">
                      <div className="text-xs font-mono text-gray-700">{formatMoney(s.total_value)}</div>
                      <div className="text-[10px] text-gray-400">{s.num_insiders} insiders</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length > 500 && (
            <div className="px-4 py-3 text-center text-xs text-gray-500 border-t border-gray-100">
              Showing first 500 of {filtered.length} signals
            </div>
          )}
        </div>
      )}
    </div>
  )
}
