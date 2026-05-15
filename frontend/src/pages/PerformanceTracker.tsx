import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { signalPerfApi, SignalPerf } from '../services/api'

type FilterMode = '30d' | '60d' | '90d' | 'all' | 'custom'
type SortKey = 'signal_date' | 'return_day0' | 'ticker' | 'total_value' | 'num_insiders'
type SortDir = 'asc' | 'desc'

export default function PerformanceTracker() {
  const [allSignals, setAllSignals] = useState<SignalPerf[]>([])
  const [loading, setLoading] = useState(true)
  const [filterMode, setFilterMode] = useState<FilterMode>('60d')
  const [selectedYear, setSelectedYear] = useState<string>('')
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  const [sortKey, setSortKey] = useState<SortKey>('signal_date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const navigate = useNavigate()

  useEffect(() => {
    let ignore = false
    setLoading(true)
    signalPerfApi.getAll('buy', false, false, 1000)
      .then((res) => {
        if (!ignore) {
          const strongBuy = (res.data || []).filter(
            (s: SignalPerf) => s.conviction_tier === 'strong_buy'
          )
          setAllSignals(strongBuy)
        }
      })
      .catch(() => { if (!ignore) setAllSignals([]) })
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [])

  // Available years
  const years = useMemo(() => {
    const s = new Set(allSignals.map(s => s.signal_date?.slice(0, 4)).filter(Boolean))
    return Array.from(s).sort().reverse()
  }, [allSignals])

  const allMonths = [
    { value: '01', label: 'January' }, { value: '02', label: 'February' },
    { value: '03', label: 'March' }, { value: '04', label: 'April' },
    { value: '05', label: 'May' }, { value: '06', label: 'June' },
    { value: '07', label: 'July' }, { value: '08', label: 'August' },
    { value: '09', label: 'September' }, { value: '10', label: 'October' },
    { value: '11', label: 'November' }, { value: '12', label: 'December' },
  ]

  // Available months — filtered to only months with data for selected year
  const availableMonths = useMemo(() => {
    if (!selectedYear) return []
    const monthsWithData = new Set(
      allSignals
        .filter(s => s.signal_date?.startsWith(selectedYear))
        .map(s => s.signal_date?.slice(5, 7))
        .filter(Boolean)
    )
    return allMonths.filter(m => monthsWithData.has(m.value))
  }, [allSignals, selectedYear])

  // Filter signals
  const filtered = useMemo(() => {
    const now = new Date()
    return allSignals.filter(s => {
      if (!s.signal_date) return false
      if (filterMode === 'all') return true
      if (filterMode === 'custom') {
        if (!selectedYear) return true
        if (!s.signal_date.startsWith(selectedYear)) return false
        if (selectedMonth && s.signal_date.slice(5, 7) !== selectedMonth) return false
        return true
      }
      const signalDate = new Date(s.signal_date + 'T12:00:00')
      const days = filterMode === '30d' ? 30 : filterMode === '60d' ? 60 : 90
      const cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000)
      return signalDate >= cutoff
    })
  }, [allSignals, filterMode, selectedYear, selectedMonth])

  // Sort
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      // Mature signals always come first
      if (a.is_mature && !b.is_mature) return -1
      if (!a.is_mature && b.is_mature) return 1

      // Within same maturity group, sort by selected key
      let av: number | string = 0, bv: number | string = 0
      if (sortKey === 'signal_date') { av = a.signal_date || ''; bv = b.signal_date || '' }
      else if (sortKey === 'return_day0') { av = a.return_day0 ?? -999; bv = b.return_day0 ?? -999 }
      else if (sortKey === 'ticker') { av = a.ticker || ''; bv = b.ticker || '' }
      else if (sortKey === 'total_value') { av = a.total_value || 0; bv = b.total_value || 0 }
      else if (sortKey === 'num_insiders') { av = a.num_insiders || 0; bv = b.num_insiders || 0 }

      if (av < bv) return sortDir === 'asc' ? -1 : 1
      if (av > bv) return sortDir === 'asc' ? 1 : -1
      return 0
    })
  }, [filtered, sortKey, sortDir])

  // Compute stats from filtered set
  const mature = filtered.filter(s => s.is_mature)
  const matureWins = mature.filter(s => (s.return_day0 ?? 0) > 0).length
  const matureLosses = mature.length - matureWins
  const hitRate = mature.length > 0 ? (matureWins / mature.length * 100) : 0
  const avgReturn = mature.length > 0
    ? mature.reduce((sum, s) => sum + (s.return_day0 ?? 0), 0) / mature.length : 0
  const withSpy = mature.filter(s => s.spy_return_90d != null)
  const avgAlpha = withSpy.length > 0
    ? withSpy.reduce((sum, s) => sum + ((s.return_day0 ?? 0) - (s.spy_return_90d ?? 0)), 0) / withSpy.length : 0

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return ''
    return sortDir === 'asc' ? ' ↑' : ' ↓'
  }

  return (
    <div>
      {/* Filter bar */}
      <div className="flex flex-wrap items-center justify-between gap-y-3 gap-x-4 mb-6">
        <div className="flex flex-wrap items-center gap-2">
          {(['30d', '60d', '90d', 'all'] as FilterMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => { setFilterMode(mode); setSelectedYear(''); setSelectedMonth('') }}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                filterMode === mode
                  ? 'bg-gray-900 text-white'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              {mode === '30d' ? 'Last 30d' : mode === '60d' ? 'Last 60d' : mode === '90d' ? 'Last 90d' : 'All Time'}
            </button>
          ))}
          <span className="hidden sm:inline text-gray-300 px-1">|</span>
          <select
            value={selectedYear}
            onChange={(e) => {
              setSelectedYear(e.target.value)
              setSelectedMonth('')  // clear month when year changes
              if (e.target.value) setFilterMode('custom')
              else { setFilterMode('60d'); setSelectedMonth('') }
            }}
            className="bg-gray-100 border-none rounded-md px-3 py-1.5 text-sm text-gray-500 font-medium"
          >
            <option value="">Year</option>
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <select
            value={selectedMonth}
            onChange={(e) => { setSelectedMonth(e.target.value); setFilterMode('custom') }}
            disabled={!selectedYear}
            className={`border-none rounded-md px-3 py-1.5 text-sm font-medium ${
              selectedYear
                ? 'bg-gray-100 text-gray-500'
                : 'bg-gray-50 text-gray-300 cursor-not-allowed'
            }`}
          >
            <option value="">{selectedYear ? 'All months' : 'Select year first'}</option>
            {availableMonths.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>
        <a
          href={signalPerfApi.getDownloadUrl('buy', false)}
          className="text-sm text-blue-700 font-medium hover:text-blue-800 whitespace-nowrap"
        >
          Download CSV ↓
        </a>
      </div>

      {/* Dynamic header stats */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3 md:flex md:gap-10 mb-6 pb-6 border-b border-gray-200">
        <div>
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Signals</div>
          <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">{filtered.length}</div>
        </div>
        <div>
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Wins / Losses</div>
          <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            <span className="text-green-700">{matureWins}</span>
            <span className="text-gray-300 text-xl"> / </span>
            <span className="text-red-800">{matureLosses}</span>
          </div>
        </div>
        <div>
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Hit Rate</div>
          <div className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            {mature.length > 0 ? `${hitRate.toFixed(1)}%` : '—'}
          </div>
        </div>
        <div>
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Avg Return</div>
          <div className={`text-2xl sm:text-3xl font-extrabold tracking-tight ${avgReturn >= 0 ? 'text-green-700' : 'text-red-800'}`}>
            {mature.length > 0 ? `${avgReturn >= 0 ? '↑ ' : '↓ '}${Math.abs(avgReturn).toFixed(1)}%` : '—'}
          </div>
        </div>
        <div>
          <div className="text-gray-600 text-xs font-semibold uppercase tracking-wider">Alpha vs SPY</div>
          <div className={`text-2xl sm:text-3xl font-extrabold tracking-tight ${avgAlpha >= 0 ? 'text-green-700' : 'text-red-800'}`}>
            {withSpy.length > 0 ? `${avgAlpha >= 0 ? '↑ ' : '↓ '}${Math.abs(avgAlpha).toFixed(1)}%` : '—'}
          </div>
        </div>
      </div>

      {/* Signal table */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Loading...</div>
      ) : (
        <div className="border-t-2 border-gray-900 overflow-x-auto">
          {/* Header */}
          <div className="grid grid-cols-[65px_1fr_55px_92px_75px_92px_75px_75px_70px_55px] gap-x-2 text-xs text-gray-600 uppercase tracking-wider py-2.5 border-b border-gray-200 min-w-[800px]">
            <span className="cursor-pointer hover:text-gray-600" onClick={() => toggleSort('ticker')}>
              Ticker{sortIndicator('ticker')}
            </span>
            <span>Company</span>
            <span>Status</span>
            <span className="cursor-pointer hover:text-gray-600" onClick={() => toggleSort('signal_date')}>
              Entry Date{sortIndicator('signal_date')}
            </span>
            <span>Entry</span>
            <span>Exit Date</span>
            <span>Exit</span>
            <span className="text-right cursor-pointer hover:text-gray-600" onClick={() => toggleSort('return_day0')}>
              Return{sortIndicator('return_day0')}
            </span>
            <span className="text-right">Alpha</span>
            <span className="text-right">Day</span>
          </div>
          {/* Rows */}
          {sorted.map((signal) => {
            const ret = signal.return_day0
            const spy = signal.spy_return_90d
            const alpha = ret != null && spy != null ? ret - spy : null
            const daysSinceSignal = signal.signal_date
              ? Math.floor((Date.now() - new Date(signal.signal_date + 'T12:00:00').getTime()) / (1000 * 60 * 60 * 24))
              : 0

            // Exit date and price depend on maturity
            let exitDate = '—'
            let exitPrice = signal.price_day90
            let displayReturn = ret
            if (signal.is_mature && signal.signal_date) {
              const sd = new Date(signal.signal_date + 'T12:00:00')
              sd.setDate(sd.getDate() + 90)
              exitDate = sd.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
            } else if (signal.price_current_date) {
              // Immature: show current price and date
              exitDate = new Date(signal.price_current_date + 'T12:00:00')
                .toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
              exitPrice = signal.price_current
              displayReturn = signal.return_current
            }

            // Format entry date
            const entryDate = signal.signal_date
              ? new Date(signal.signal_date + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
              : '—'

            return (
              <a
                key={signal.signal_id}
                href={`/signal/${signal.signal_id}`}
                onClick={(e) => { if (!e.ctrlKey && !e.metaKey) { e.preventDefault(); navigate(`/signal/${signal.signal_id}`) } }}
                className="grid grid-cols-[65px_1fr_55px_92px_75px_92px_75px_75px_70px_55px] gap-x-2 py-2.5 border-b border-gray-100 items-center cursor-pointer hover:bg-gray-50 transition-colors min-w-[800px] no-underline text-inherit"
              >
                <span className="font-bold text-sm">{signal.ticker}</span>
                <span className="text-gray-500 text-sm truncate">{signal.company_name}</span>
                <span>
                  {signal.is_mature ? (
                    <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                      (ret ?? 0) > 0 ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-800'
                    }`}>
                      90d
                    </span>
                  ) : (
                    <span className={`inline-block w-2 h-2 rounded-full ${
                      (ret ?? 0) > 0 ? 'bg-green-500' : 'bg-red-500'
                    }`} />
                  )}
                </span>
                <span className="text-sm text-gray-600">{entryDate}</span>
                <span className="text-sm" style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {signal.price_day0 ? `$${signal.price_day0.toFixed(2)}` : '—'}
                </span>
                <span className="text-sm text-gray-600">{exitDate}</span>
                <span className="text-sm" style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {exitPrice ? `$${exitPrice.toFixed(2)}` : '—'}
                </span>
                <span
                  className={`text-right text-sm font-semibold ${
                    displayReturn != null ? (displayReturn >= 0 ? 'text-green-700' : 'text-red-800') : 'text-gray-300'
                  }`}
                  style={{ fontVariantNumeric: 'tabular-nums' }}
                >
                  {displayReturn != null ? `${displayReturn >= 0 ? '↑ ' : '↓ '}${Math.abs(displayReturn).toFixed(1)}%` : '—'}
                </span>
                <span
                  className={`text-right text-sm font-semibold ${
                    alpha != null ? (alpha >= 0 ? 'text-green-700' : 'text-red-800') : 'text-gray-300'
                  }`}
                  style={{ fontVariantNumeric: 'tabular-nums' }}
                >
                  {alpha != null ? `${alpha >= 0 ? '↑ ' : '↓ '}${Math.abs(alpha).toFixed(1)}%` : '—'}
                </span>
                <span className="text-right text-sm text-gray-500">
                  {signal.is_mature ? '90' : daysSinceSignal}
                </span>
              </a>
            )
          })}
        </div>
      )}

      {/* Footer */}
      <div className="mt-4 text-xs text-gray-500">
        Showing {sorted.length} strong_buy signals. Returns are 90-day forward from signal date. Alpha = signal return minus SPY return.
      </div>
    </div>
  )
}
