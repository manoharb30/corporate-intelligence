import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  signalPerfApi,
  SignalPerf,
  SignalPerfSummary,
  DelayedEntryStats,
  ConvictionLadderEntry,
  IndustryBreakdown,
} from '../services/api'

function pct(v: number | null | undefined, fallback = '—'): string {
  if (v == null) return fallback
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}

function price(v: number | null | undefined): string {
  if (v == null) return '—'
  return `$${v.toFixed(2)}`
}

type Tab = 'all' | 'buy' | 'sell'
type SortKey = 'signal_date' | 'return_day0' | 'num_insiders' | 'ticker'

export default function TrackRecord() {
  const [summary, setSummary] = useState<SignalPerfSummary | null>(null)
  const [signals, setSignals] = useState<SignalPerf[]>([])
  const [delayedEntry, setDelayedEntry] = useState<DelayedEntryStats | null>(null)
  const [ladder, setLadder] = useState<ConvictionLadderEntry[]>([])
  const [industries, setIndustries] = useState<IndustryBreakdown[]>([])
  const [loading, setLoading] = useState(true)
  const [computing, setComputing] = useState(false)
  const [tab, setTab] = useState<Tab>('all')
  const [sortKey, setSortKey] = useState<SortKey>('signal_date')
  const [sortAsc, setSortAsc] = useState(false)
  const [meaningfulOnly, setMeaningfulOnly] = useState(true)

  const loadData = (meaningful: boolean) => {
    setLoading(true)
    Promise.all([
      signalPerfApi.getSummary(meaningful),
      signalPerfApi.getAll(undefined, true, meaningful, 500),
      signalPerfApi.getDelayedEntry(meaningful),
      signalPerfApi.getConvictionLadder(meaningful),
      signalPerfApi.getIndustry(meaningful),
    ])
      .then(([sumRes, sigRes, deRes, ladRes, indRes]) => {
        setSummary(sumRes.data)
        setSignals(sigRes.data)
        setDelayedEntry(deRes.data)
        setLadder(ladRes.data)
        setIndustries(indRes.data)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData(meaningfulOnly)
  }, [meaningfulOnly])

  const handleCompute = async () => {
    setComputing(true)
    try {
      await signalPerfApi.compute(365)
      loadData(meaningfulOnly)
    } catch {
      // ignore
    } finally {
      setComputing(false)
    }
  }

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc)
    } else {
      setSortKey(key)
      setSortAsc(false)
    }
  }

  const filteredSignals = signals
    .filter(s => tab === 'all' || s.direction === tab)
    .sort((a, b) => {
      let cmp = 0
      if (sortKey === 'signal_date') cmp = a.signal_date.localeCompare(b.signal_date)
      else if (sortKey === 'return_day0') cmp = (a.return_day0 ?? -999) - (b.return_day0 ?? -999)
      else if (sortKey === 'num_insiders') cmp = a.num_insiders - b.num_insiders
      else if (sortKey === 'ticker') cmp = (a.ticker || '').localeCompare(b.ticker || '')
      return sortAsc ? cmp : -cmp
    })

  const buySignals = signals.filter(s => s.direction === 'buy')
  const sellSignals = signals.filter(s => s.direction === 'sell')

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full"></div>
      </div>
    )
  }

  const noData = signals.length === 0

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <section className="py-8 mb-6">
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
            Track Record
          </h1>
          <div className="flex items-center gap-3">
            <a
              href={signalPerfApi.getDownloadUrl(tab === 'all' ? undefined : tab)}
              download
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Download CSV
            </a>
            <button
              onClick={handleCompute}
              disabled={computing}
              className="px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {computing ? 'Computing...' : 'Recompute'}
            </button>
          </div>
        </div>
        <p className="text-gray-500 mb-4">
          Every signal we fired, every price that followed. All data verifiable from SEC EDGAR.
        </p>

        {/* Meaningful trades toggle */}
        <div className="flex items-center gap-3 bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 w-fit">
          <span className="text-sm text-gray-600">Filter:</span>
          <button
            onClick={() => setMeaningfulOnly(true)}
            className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
              meaningfulOnly
                ? 'bg-gray-900 text-white'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Meaningful Trades
          </button>
          <button
            onClick={() => setMeaningfulOnly(false)}
            className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
              !meaningfulOnly
                ? 'bg-gray-900 text-white'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            All Signals
          </button>
          <span className="text-xs text-gray-400 ml-2">
            {meaningfulOnly ? 'Trades 0.01-1% of market cap' : 'Including routine compensation selling'}
          </span>
        </div>
      </section>

      {noData ? (
        <div className="text-center py-16">
          <p className="text-gray-500 mb-4">No signal performance data computed yet.</p>
          <button
            onClick={handleCompute}
            disabled={computing}
            className="px-6 py-3 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50"
          >
            {computing ? 'Computing... (this takes a few minutes)' : 'Compute Track Record'}
          </button>
        </div>
      ) : (
        <>
          {/* Section 1: Summary Stats */}
          {summary && summary.total_mature > 0 && (
            <section className="mb-10">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-green-50 border border-green-200 rounded-xl p-5">
                  <div className="text-3xl font-black text-green-700">{summary.buy_win_rate?.toFixed(1) ?? '—'}%</div>
                  <div className="text-xs font-semibold text-green-600 uppercase mt-1">Buy Win Rate</div>
                  <div className="text-xs text-green-600 mt-0.5">{summary.buy_count} signals scored</div>
                </div>
                <div className="bg-green-50 border border-green-200 rounded-xl p-5">
                  <div className="text-3xl font-black text-green-700">{pct(summary.buy_avg_return_30d)}</div>
                  <div className="text-xs font-semibold text-green-600 uppercase mt-1">Avg Buy 30d Return</div>
                  <div className="text-xs text-green-600 mt-0.5">SPY: {pct(summary.avg_spy_return)}</div>
                </div>
                <div className="bg-red-50 border border-red-200 rounded-xl p-5">
                  <div className="text-3xl font-black text-red-700">{summary.sell_correct_rate?.toFixed(1) ?? '—'}%</div>
                  <div className="text-xs font-semibold text-red-600 uppercase mt-1">Sell Correct Rate</div>
                  <div className="text-xs text-red-600 mt-0.5">{summary.sell_count} signals scored</div>
                </div>
                <div className="bg-purple-50 border border-purple-200 rounded-xl p-5">
                  <div className="text-3xl font-black text-purple-700">{summary.eight_k_follow_rate?.toFixed(0) ?? '—'}%</div>
                  <div className="text-xs font-semibold text-purple-600 uppercase mt-1">8-K Confirmation</div>
                  <div className="text-xs text-purple-600 mt-0.5">Buy signals followed by filing</div>
                </div>
              </div>
            </section>
          )}

          {/* Section 2: Delayed Entry Analysis */}
          {delayedEntry && (
            <section className="mb-10">
              <h2 className="text-xl font-bold text-gray-900 mb-1">Delayed Entry Analysis</h2>
              <p className="text-sm text-gray-500 mb-4">
                Fixed 30-day return window. Shows how much alpha remains if you enter 1, 2, 3, 5, or 7 days after the signal.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {delayedEntry.buy && (
                  <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-green-100 text-green-700">BUY</span>
                      <span className="text-xs text-gray-400">{delayedEntry.buy.n} signals</span>
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-gray-500 uppercase border-b border-gray-100">
                          <th className="text-left py-1.5">Entry</th>
                          <th className="text-right py-1.5">Avg 30d Return</th>
                          <th className="text-right py-1.5">vs Day 0</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(delayedEntry.buy.entries).map(([day, data]) => {
                          const baseReturn = delayedEntry.buy!.entries.day0?.avg_return ?? 0
                          const diff = data.avg_return - baseReturn
                          return (
                            <tr key={day} className="border-b border-gray-50">
                              <td className="py-1.5 font-medium text-gray-800">
                                {day === 'day0' ? 'Same day' : `+${day.replace('day', '')}d`}
                              </td>
                              <td className={`py-1.5 text-right font-bold ${data.avg_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {pct(data.avg_return)}
                              </td>
                              <td className={`py-1.5 text-right text-xs ${diff >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {day === 'day0' ? '—' : pct(diff)}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                {delayedEntry.sell && (
                  <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-700">SELL (Short Return)</span>
                      <span className="text-xs text-gray-400">{delayedEntry.sell.n} signals</span>
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-gray-500 uppercase border-b border-gray-100">
                          <th className="text-left py-1.5">Entry</th>
                          <th className="text-right py-1.5">Avg 30d Short</th>
                          <th className="text-right py-1.5">vs Day 0</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(delayedEntry.sell.entries).map(([day, data]) => {
                          const baseReturn = delayedEntry.sell!.entries.day0?.avg_return ?? 0
                          const diff = data.avg_return - baseReturn
                          return (
                            <tr key={day} className="border-b border-gray-50">
                              <td className="py-1.5 font-medium text-gray-800">
                                {day === 'day0' ? 'Same day' : `+${day.replace('day', '')}d`}
                              </td>
                              <td className={`py-1.5 text-right font-bold ${data.avg_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {pct(data.avg_return)}
                              </td>
                              <td className={`py-1.5 text-right text-xs ${diff >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                {day === 'day0' ? '—' : pct(diff)}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Section 3: Conviction Ladder */}
          {ladder.length > 0 && (
            <section className="mb-10">
              <h2 className="text-xl font-bold text-gray-900 mb-1">Conviction Ladder</h2>
              <p className="text-sm text-gray-500 mb-4">
                Sell signal accuracy scales with seller count. More insiders selling = higher conviction.
              </p>
              <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-100">
                      <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Sellers</th>
                      <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Signals</th>
                      <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Correct</th>
                      <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Correct Rate</th>
                      <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Avg Short Return</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ladder.map(row => (
                      <tr key={row.threshold} className="border-b border-gray-50">
                        <td className="px-4 py-2.5 font-bold text-gray-900">{row.threshold} sellers</td>
                        <td className="px-4 py-2.5 text-right text-gray-600">{row.total}</td>
                        <td className="px-4 py-2.5 text-right text-gray-600">{row.correct}</td>
                        <td className="px-4 py-2.5 text-right font-bold text-red-700">{row.correct_rate?.toFixed(1)}%</td>
                        <td className={`px-4 py-2.5 text-right font-bold ${row.avg_short_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {pct(row.avg_short_return)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Section 4: Industry Breakdown */}
          {industries.length > 0 && (
            <section className="mb-10">
              <h2 className="text-xl font-bold text-gray-900 mb-1">Performance by Industry</h2>
              <p className="text-sm text-gray-500 mb-4">
                Buy signal win rates by sector. Minimum 3 signals per industry.
              </p>
              <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-100">
                      <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Industry</th>
                      <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Signals</th>
                      <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Win Rate</th>
                      <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Avg Return</th>
                    </tr>
                  </thead>
                  <tbody>
                    {industries.map(row => (
                      <tr key={row.industry} className="border-b border-gray-50">
                        <td className="px-4 py-2.5 text-gray-900 truncate max-w-[300px]">{row.industry}</td>
                        <td className="px-4 py-2.5 text-right text-gray-600">{row.total}</td>
                        <td className={`px-4 py-2.5 text-right font-bold ${(row.win_rate ?? 0) >= 60 ? 'text-green-600' : 'text-red-600'}`}>
                          {row.win_rate?.toFixed(1)}%
                        </td>
                        <td className={`px-4 py-2.5 text-right font-bold ${(row.avg_return ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {pct(row.avg_return)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Section 5: Per-Ticker Signal Table */}
          <section className="mb-10">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-bold text-gray-900 mb-1">All Signals</h2>
                <p className="text-sm text-gray-500">
                  {filteredSignals.length} mature signals with day-by-day price data
                </p>
              </div>
              <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                {(['all', 'buy', 'sell'] as Tab[]).map(t => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                      tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    {t === 'all' ? `All (${signals.length})` : t === 'buy' ? `Buy (${buySignals.length})` : `Sell (${sellSignals.length})`}
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
              <table className="w-full text-sm whitespace-nowrap">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    <th
                      className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                      onClick={() => handleSort('ticker')}
                    >
                      Ticker {sortKey === 'ticker' ? (sortAsc ? '↑' : '↓') : ''}
                    </th>
                    <th className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase">Type</th>
                    <th
                      className="text-left px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                      onClick={() => handleSort('signal_date')}
                    >
                      Date {sortKey === 'signal_date' ? (sortAsc ? '↑' : '↓') : ''}
                    </th>
                    <th
                      className="text-right px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                      onClick={() => handleSort('num_insiders')}
                    >
                      Insiders {sortKey === 'num_insiders' ? (sortAsc ? '↑' : '↓') : ''}
                    </th>
                    <th className="text-right px-2 py-2.5 text-xs font-semibold text-gray-500 uppercase">Day 0</th>
                    <th className="text-right px-2 py-2.5 text-xs font-semibold text-gray-500 uppercase">Day 1</th>
                    <th className="text-right px-2 py-2.5 text-xs font-semibold text-gray-500 uppercase">Day 2</th>
                    <th className="text-right px-2 py-2.5 text-xs font-semibold text-gray-500 uppercase">Day 3</th>
                    <th className="text-right px-2 py-2.5 text-xs font-semibold text-gray-500 uppercase">Day 5</th>
                    <th className="text-right px-2 py-2.5 text-xs font-semibold text-gray-500 uppercase">Day 7</th>
                    <th className="text-right px-2 py-2.5 text-xs font-semibold text-gray-500 uppercase">Day 30</th>
                    <th
                      className="text-right px-3 py-2.5 text-xs font-semibold text-gray-500 uppercase cursor-pointer hover:text-gray-700"
                      onClick={() => handleSort('return_day0')}
                    >
                      30d Return {sortKey === 'return_day0' ? (sortAsc ? '↑' : '↓') : ''}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSignals.map((s, idx) => {
                    const isBuy = s.direction === 'buy'
                    const ret = s.return_day0
                    const retColor = ret == null ? '' : isBuy
                      ? (ret >= 0 ? 'text-green-600' : 'text-red-600')
                      : (ret <= 0 ? 'text-green-600' : 'text-red-600')

                    return (
                      <tr key={s.signal_id + idx} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="px-3 py-2">
                          <Link
                            to={`/signal/${encodeURIComponent(s.signal_id)}`}
                            className="font-bold text-gray-900 hover:text-primary-600"
                          >
                            {s.ticker}
                          </Link>
                          <div className="text-xs text-gray-400 truncate max-w-[120px]">{s.company_name}</div>
                        </td>
                        <td className="px-3 py-2">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                            isBuy ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                          }`}>
                            {isBuy ? 'BUY' : 'SELL'}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-600 font-mono">{s.signal_date}</td>
                        <td className="px-3 py-2 text-right text-gray-800 font-medium">{s.num_insiders}</td>
                        <td className="px-2 py-2 text-right text-xs font-mono text-gray-600">{price(s.price_day0)}</td>
                        <td className="px-2 py-2 text-right text-xs font-mono text-gray-600">{price(s.price_day1)}</td>
                        <td className="px-2 py-2 text-right text-xs font-mono text-gray-600">{price(s.price_day2)}</td>
                        <td className="px-2 py-2 text-right text-xs font-mono text-gray-600">{price(s.price_day3)}</td>
                        <td className="px-2 py-2 text-right text-xs font-mono text-gray-600">{price(s.price_day5)}</td>
                        <td className="px-2 py-2 text-right text-xs font-mono text-gray-600">{price(s.price_day7)}</td>
                        <td className="px-2 py-2 text-right text-xs font-mono text-gray-600">{price(s.price_day30)}</td>
                        <td className={`px-3 py-2 text-right font-bold ${retColor}`}>
                          {pct(ret)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
