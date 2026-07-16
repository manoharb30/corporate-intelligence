import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { portfolioApi, PortfolioSnapshot } from '../services/api'

function fmtUsd(v: number | null | undefined, decimals = 2) {
  if (v == null) return '—'
  return '$' + v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function fmtDate(d: string | null | undefined) {
  if (!d) return '—'
  return new Date(d.slice(0, 10) + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

// All market-facing timestamps render in US Eastern time, explicitly labeled.
function fmtET(iso: string | null | undefined, withDate = true) {
  if (!iso) return '—'
  const opts: Intl.DateTimeFormatOptions = {
    timeZone: 'America/New_York',
    hour: '2-digit', minute: '2-digit', hour12: false,
    ...(withDate ? { month: 'short' as const, day: 'numeric' as const } : {}),
  }
  return new Intl.DateTimeFormat('en-US', opts).format(new Date(iso)) + ' ET'
}

function PnlText({ value, pct, className = '' }: { value: number; pct?: number | null; className?: string }) {
  const up = value >= 0
  return (
    <span className={`${up ? 'text-green-600' : 'text-red-600'} ${className}`}>
      {up ? '+' : ''}{fmtUsd(value)}{pct != null && ` (${up ? '+' : ''}${pct.toFixed(2)}%)`}
    </span>
  )
}

type CurvePoint = { date: string; equity: number }

function EquityCurve({ curve, spy }: { curve: CurvePoint[]; spy: CurvePoint[] }) {
  if (curve.length < 2) {
    return (
      <div className="text-center text-gray-500 text-sm py-10">
        Equity curve appears after the first two trading days.
      </div>
    )
  }
  const W = 920, H = 250, L = 62, R = 130, T = 14, B = 30
  const plotW = W - L - R, plotH = H - T - B
  const all = [...curve.map((c) => c.equity), ...spy.map((s) => s.equity)]
  const pad = Math.max((Math.max(...all) - Math.min(...all)) * 0.15, 50)
  const yMin = Math.min(...all) - pad
  const yMax = Math.max(...all) + pad
  const dates = curve.map((c) => c.date)
  const xOf = (d: string) => {
    const i = dates.indexOf(d)
    return L + ((i < 0 ? 0 : i) / (dates.length - 1)) * plotW
  }
  const y = (v: number) => T + (1 - (v - yMin) / (yMax - yMin)) * plotH
  const pathOf = (pts: CurvePoint[]) =>
    pts.filter((p) => dates.includes(p.date))
      .map((p, i) => `${i ? 'L' : 'M'}${xOf(p.date).toFixed(1)} ${y(p.equity).toFixed(1)}`).join(' ')
  const portPath = pathOf(curve)
  const spyPath = pathOf(spy)
  const area = `${portPath} L ${xOf(dates[dates.length - 1])} ${y(yMin)} L ${xOf(dates[0])} ${y(yMin)} Z`
  const labelIdx = [0, Math.floor((dates.length - 1) / 2), dates.length - 1]
  const last = curve[curve.length - 1]
  const spyLast = spy.length ? spy[spy.length - 1] : null
  const precision = yMax - yMin < 2000 ? 2 : 1

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
      aria-label={`Portfolio vs SPY benchmark, ${dates[0]} to ${dates[dates.length - 1]}, both starting at $100,000`}>
      {Array.from({ length: 5 }, (_, i) => {
        const v = yMin + ((yMax - yMin) * i) / 4
        return (
          <g key={i}>
            <line x1={L} y1={y(v)} x2={L + plotW} y2={y(v)} stroke="#e5e7eb" strokeWidth={1} />
            <text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize={11} fill="#9ca3af">
              {(v / 1000).toFixed(precision)}K
            </text>
          </g>
        )
      })}
      {labelIdx.map((i) => (
        <text key={i} x={xOf(dates[i])} y={H - 8} textAnchor="middle" fontSize={11} fill="#9ca3af">
          {fmtDate(dates[i])}
        </text>
      ))}
      <path d={area} fill="#0078f8" opacity={0.08} />
      {spyPath && (
        <path d={spyPath} fill="none" stroke="#8b97ab" strokeWidth={2} strokeDasharray="5 4" />
      )}
      <path d={portPath} fill="none" stroke="#0078f8" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
      {spyLast && (
        <g>
          <circle cx={xOf(spyLast.date)} cy={y(spyLast.equity)} r={3.5} fill="#8b97ab" />
          <text x={xOf(spyLast.date) + 8} y={y(spyLast.equity) - 5} fontSize={11} fill="#6b7280">SPY (benchmark)</text>
          <text x={xOf(spyLast.date) + 8} y={y(spyLast.equity) + 9} fontSize={11} fontWeight={700} fill="#6b7280">
            {fmtUsd(spyLast.equity, 0)}
          </text>
        </g>
      )}
      <circle cx={xOf(last.date)} cy={y(last.equity)} r={4.5} fill="#0078f8" stroke="#fff" strokeWidth={2} />
      <text x={xOf(last.date) + 8} y={y(last.equity) + (spyLast && Math.abs(y(spyLast.equity) - y(last.equity)) < 28 ? 22 : -5)} fontSize={11} fill="#0078f8">LookInsight Portfolio</text>
      <text x={xOf(last.date) + 8} y={y(last.equity) + (spyLast && Math.abs(y(spyLast.equity) - y(last.equity)) < 28 ? 36 : 9)} fontSize={11} fontWeight={700} fill="#0078f8">
        {fmtUsd(last.equity, 0)}
      </text>
    </svg>
  )
}

export default function Portfolio() {
  const [snap, setSnap] = useState<PortfolioSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let ignore = false
    portfolioApi.getSnapshot()
      .then((res) => { if (!ignore) setSnap(res.data) })
      .catch(() => { if (!ignore) setError(true) })
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [])

  if (loading) {
    return <div className="max-w-7xl mx-auto px-4 py-16 text-center text-gray-500">Loading portfolio…</div>
  }
  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-gray-500">
        Portfolio service unavailable — Alpaca API could not be reached.
      </div>
    )
  }
  if (!snap?.configured) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-gray-500">
        Portfolio not configured — Alpaca API keys missing on the server.
      </div>
    )
  }

  const acct = snap.account!
  const alloc = snap.allocation!
  const positions = snap.positions ?? []
  const skips = snap.skipped_signals ?? []
  const maxPositions = snap.max_positions ?? 20

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 mb-1">
        <h1 className="text-2xl font-bold text-gray-900">Portfolio</h1>
        <span className="text-[11px] font-bold tracking-wider uppercase text-amber-700 bg-amber-50 border border-amber-300 rounded-full px-2.5 py-0.5">
          Paper Trading
        </span>
      </div>
      <p className="text-sm text-gray-500 mb-6">
        Alpaca paper account · {fmtUsd(acct.initial_capital, 0)} initial · inception {fmtDate(snap.inception_date)} · as of {fmtET(snap.as_of)}
      </p>

      {/* Tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Account value</div>
          <div className="text-2xl font-bold text-gray-900 tabular-nums">{fmtUsd(acct.value)}</div>
          <div className="text-xs mt-1 font-semibold tabular-nums">
            <PnlText value={acct.pnl} pct={acct.pnl_pct} /> <span className="text-gray-400 font-normal">since inception</span>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Invested in signals</div>
          <div className="text-2xl font-bold text-gray-900 tabular-nums">{fmtUsd(snap.positions_value)}</div>
          <div className="text-xs mt-1 text-gray-500 tabular-nums">
            {positions.length} of {maxPositions} position slots filled
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Treasury sweep (SGOV)</div>
          <div className="text-2xl font-bold text-gray-900 tabular-nums">{fmtUsd(snap.sweep?.market_value ?? 0)}</div>
          <div className="text-xs mt-1 text-gray-500 tabular-nums">
            {snap.sweep ? `${snap.sweep.qty.toLocaleString()} sh` : 'no sweep position yet'}
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Cash buffer</div>
          <div className="text-2xl font-bold text-gray-900 tabular-nums">{fmtUsd(acct.cash)}</div>
          <div className="text-xs mt-1 text-gray-500">operational buffer (~1%); signal slices are funded by liquidating the Treasury sweep</div>
        </div>
      </div>

      {/* Allocation */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-4">
        <div className="px-5 py-3.5 border-b border-gray-200 flex flex-wrap items-center gap-3">
          <h2 className="text-sm font-bold text-gray-900">Allocation</h2>
          <span className="text-xs text-gray-400 tabular-nums">
            {maxPositions} position slots · {positions.length} filled
          </span>
        </div>
        <div className="p-5">
          <div className="flex gap-0.5 h-3.5 rounded-full overflow-hidden" role="img"
            aria-label={`Allocation: signal positions ${alloc.positions_pct}%, Treasury sweep ${alloc.sweep_pct}%, cash ${alloc.cash_pct}%`}>
            <div className="bg-blue-600" style={{ width: `${alloc.positions_pct}%` }} />
            <div className="bg-blue-300" style={{ width: `${alloc.sweep_pct}%` }} />
            <div className="bg-gray-300" style={{ width: `${alloc.cash_pct}%` }} />
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 mt-2.5 text-xs text-gray-500 tabular-nums">
            <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-blue-600 mr-1.5 align-[-1px]" />Signal positions · {alloc.positions_pct}%</span>
            <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-blue-300 mr-1.5 align-[-1px]" />Treasury sweep · {alloc.sweep_pct}%</span>
            <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-gray-300 mr-1.5 align-[-1px]" />Cash · {alloc.cash_pct}%</span>
          </div>
        </div>
      </div>

      {/* Equity curve vs SPY */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-4">
        <div className="px-5 py-3.5 border-b border-gray-200 flex flex-wrap items-center gap-x-4 gap-y-1">
          <h2 className="text-sm font-bold text-gray-900">Equity curve vs SPY</h2>
          <span className="text-xs text-gray-400">
            daily close · both series start at {fmtUsd(acct.initial_capital, 0)} on {fmtDate(snap.inception_date)} (inception)
          </span>
          <div className="flex gap-4 ml-auto text-xs text-gray-500">
            <span className="inline-flex items-center gap-1.5">
              <svg width="20" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="#0078f8" strokeWidth="2.5" /></svg>
              LookInsight Portfolio
            </span>
            <span className="inline-flex items-center gap-1.5">
              <svg width="20" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="#8b97ab" strokeWidth="2" strokeDasharray="4 3" /></svg>
              SPY (benchmark)
            </span>
          </div>
        </div>
        <div className="p-5">
          <EquityCurve curve={snap.equity_curve ?? []} spy={snap.spy_curve ?? []} />
        </div>
      </div>

      {/* Open positions */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-4">
        <div className="px-5 py-3.5 border-b border-gray-200 flex flex-wrap items-center gap-3">
          <h2 className="text-sm font-bold text-gray-900">Open positions</h2>
          <span className="text-xs text-gray-400 tabular-nums">
            {positions.length >= 10 && snap.avg_shortfall_pct != null &&
              `on average we bought ${Math.abs(snap.avg_shortfall_pct)}% ${snap.avg_shortfall_pct >= 0 ? 'above' : 'below'} the signal-day price · `}
            each position is sold 90 days after its signal
          </span>
        </div>
        {positions.length === 0 && !snap.sweep ? (
          <div className="text-center text-gray-500 text-sm py-10">
            <div className="font-semibold text-gray-700 mb-1">No open positions yet</div>
            The next strong_buy signal opens the first $5K slice.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular-nums">
              <thead>
                <tr className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 border-b border-gray-200">
                  <th className="text-left px-4 py-2.5">Company</th>
                  <th className="text-left px-4 py-2.5">Signal date</th>
                  <th className="text-right px-4 py-2.5">Price at signal</th>
                  <th className="text-right px-4 py-2.5">Our buy price</th>
                  <th className="text-right px-4 py-2.5 cursor-help underline decoration-dotted decoration-gray-300"
                    title="Average fill price vs the stock's closing price on signal day (day-0 reference). Negative = we filled below the day-0 price.">
                    Buy vs signal
                  </th>
                  <th className="text-right px-4 py-2.5">Invested</th>
                  <th className="text-right px-4 py-2.5">Price now</th>
                  <th className="text-right px-4 py-2.5">Value now</th>
                  <th className="text-right px-4 py-2.5">Today's P/L</th>
                  <th className="text-right px-4 py-2.5">Total P/L</th>
                  <th className="text-left px-4 py-2.5">Sell date (day 90)</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.ticker} className="border-b border-gray-100 hover:bg-blue-50/40">
                    <td className="px-4 py-3">
                      {p.signal_id ? (
                        <Link to={`/signal/${p.signal_id}`} className="font-bold text-blue-700 hover:underline">{p.ticker}</Link>
                      ) : (
                        <span className="font-bold text-gray-900">{p.ticker}</span>
                      )}
                      {p.company_name && <div className="text-xs text-gray-500">{p.company_name}</div>}
                      {p.is_launch_trade && (
                        <div className="mt-1.5">
                          <span className="text-[10px] font-semibold rounded-full px-2 py-0.5 bg-gray-100 text-gray-500 border border-gray-200"
                            title="Opened at system launch (T+3 from signal). Steady-state entries execute on the first trading day after signal detection.">
                            LAUNCH TRADE · T+3
                          </span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {p.signal_id ? (
                        <Link to={`/signal/${p.signal_id}`} className="text-blue-700 hover:underline">{fmtDate(p.signal_date)}</Link>
                      ) : (
                        <div>{fmtDate(p.signal_date)}</div>
                      )}
                      {p.num_insiders != null && (
                        <div className="text-xs text-gray-500">
                          {p.num_insiders} insiders{p.cluster_value ? ` · ${fmtUsd(p.cluster_value, 0)} cluster` : ''}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">{p.day0_price != null ? fmtUsd(p.day0_price) : '—'}</td>
                    <td className="px-4 py-3 text-right">{fmtUsd(p.avg_fill)}</td>
                    <td className="px-4 py-3 text-right">
                      {p.shortfall_pct != null ? (
                        <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${p.shortfall_pct > 0 ? 'bg-amber-50 text-amber-700' : 'bg-green-50 text-green-700'}`}
                          title="Average fill price vs the signal-day closing price. Negative = filled below day-0.">
                          {p.shortfall_pct >= 0 ? '+' : ''}{p.shortfall_pct}%
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">{fmtUsd(p.cost_basis)}</td>
                    <td className="px-4 py-3 text-right">{fmtUsd(p.last_price)}</td>
                    <td className="px-4 py-3 text-right">{fmtUsd(p.market_value)}</td>
                    <td className="px-4 py-3 text-right">
                      <PnlText value={p.today_pl} className="font-semibold" />
                      <div className={`text-xs ${p.today_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {p.today_plpc >= 0 ? '+' : ''}{p.today_plpc}%
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <PnlText value={p.unrealized_pl} className="font-semibold" />
                      <div className={`text-xs ${p.unrealized_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {p.unrealized_plpc >= 0 ? '+' : ''}{p.unrealized_plpc}%
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div>{fmtDate(p.exit_date)}</div>
                      {p.days_left != null && <div className="text-xs text-gray-500">{p.days_left} days left</div>}
                    </td>
                  </tr>
                ))}
                {snap.sweep && (
                  <tr className="border-b border-gray-100 bg-gray-50/60">
                    <td className="px-4 py-3">
                      <div className="font-bold text-gray-900">{snap.sweep.ticker}</div>
                      <div className="text-xs text-gray-500">Cash reserve — US Treasury ETF</div>
                    </td>
                    <td className="px-4 py-3 text-gray-400">—</td>
                    <td className="px-4 py-3 text-right text-gray-400">—</td>
                    <td className="px-4 py-3 text-right">{fmtUsd(snap.sweep.avg_fill)}</td>
                    <td className="px-4 py-3 text-right text-gray-400">—</td>
                    <td className="px-4 py-3 text-right">{fmtUsd(snap.sweep.cost_basis)}</td>
                    <td className="px-4 py-3 text-right">{fmtUsd(snap.sweep.last_price)}</td>
                    <td className="px-4 py-3 text-right">{fmtUsd(snap.sweep.market_value)}</td>
                    <td className="px-4 py-3 text-right">
                      <PnlText value={snap.sweep.today_pl} className="font-semibold" />
                      <div className={`text-xs ${snap.sweep.today_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {snap.sweep.today_plpc >= 0 ? '+' : ''}{snap.sweep.today_plpc}%
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <PnlText value={snap.sweep.unrealized_pl} className="font-semibold" />
                      <div className={`text-xs ${snap.sweep.unrealized_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {snap.sweep.unrealized_plpc >= 0 ? '+' : ''}{snap.sweep.unrealized_plpc}%
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">sold when a new<br />signal needs cash</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Skipped signals */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-4">
        <div className="px-5 py-3.5 border-b border-gray-200">
          <h2 className="text-sm font-bold text-gray-900">Skipped signals <span className="font-normal text-xs text-gray-400 ml-2">capacity log</span></h2>
        </div>
        {skips.length === 0 ? (
          <div className="px-5 py-4 text-sm text-gray-600">
            0 signals skipped since inception — every strong_buy signal has been taken.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular-nums">
              <thead>
                <tr className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 border-b border-gray-200">
                  <th className="text-left px-4 py-2.5">Signal</th>
                  <th className="text-left px-4 py-2.5">Signal date</th>
                  <th className="text-left px-4 py-2.5">Reason</th>
                  <th className="text-left px-4 py-2.5">Logged</th>
                </tr>
              </thead>
              <tbody>
                {skips.map((s) => (
                  <tr key={s.signal_id} className="border-b border-gray-100">
                    <td className="px-4 py-2.5">
                      <Link to={`/signal/${s.signal_id}`} className="font-bold text-blue-700 hover:underline">{s.ticker}</Link>
                    </td>
                    <td className="px-4 py-2.5">{fmtDate(s.signal_date)}</td>
                    <td className="px-4 py-2.5">{s.reason}</td>
                    <td className="px-4 py-2.5 text-gray-500">{fmtET(s.logged_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Methodology — pre-registered spec */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-6">
        <div className="px-5 py-3.5 border-b border-gray-200">
          <h2 className="text-sm font-bold text-gray-900">Methodology <span className="font-normal text-xs text-gray-400 ml-2">effective July 16, 2026</span></h2>
        </div>
        <div className="px-5 py-4 text-[13px] text-gray-600 leading-relaxed space-y-2.5">
          <p><span className="font-semibold text-gray-800">Entry.</span> Positions are opened manually after a strong_buy
            signal is generated — on the first trading day after the signal is detected and reviewed (signal detection
            currently runs on an operator schedule, not an automated daily job). Each entry is a fixed $5,000 notional,
            executed as 3 market-order tranches at fixed clock times: <span className="font-semibold">10:00, 12:30 and
            15:30 ET</span>. If entry begins mid-session, the remaining tranches compress into what is left of that day.</p>
          <p><span className="font-semibold text-gray-800">Sizing &amp; capacity.</span> Fixed $5,000 per signal;
            maximum {maxPositions} concurrent positions. Signals arriving while all slots are filled are skipped and
            recorded in the capacity log above — never entered late.</p>
          <p><span className="font-semibold text-gray-800">Exit.</span> Each position is sold 90 days after its signal
            date, in 3 same-day tranches mirroring the entry. No stop-loss, no take-profit, no discretionary overrides
            after a signal is published. (Signal <em>generation</em>, upstream of this portfolio, applies a documented
            exclusion list before publication; once published, execution is mechanical.)</p>
          <p><span className="font-semibold text-gray-800">Benchmark &amp; measurement.</span> Performance is compared
            against SPY normalized to the same starting capital at inception ({fmtDate(snap.inception_date)}). Every
            position records the signal-day closing price next to the actual average fill ("Buy vs signal"), so live
            results stay comparable to the published signal statistics.</p>
          <p><span className="font-semibold text-gray-800">Idle cash.</span> Swept into a short-duration US Treasury
            ETF (SGOV) and liquidated to fund new positions. The sweep's yield is cash management, not part of the
            signal offering; the paper account may not credit fund distributions.</p>
          <p><span className="font-semibold text-gray-800">Fills disclosure.</span> Fills are simulated via Alpaca
            paper trading; live execution would incur additional slippage and market impact.</p>
          <p><span className="font-semibold text-gray-800">Changelog.</span> No methodology changes since inception.
            Any future change is appended here with its date and is never applied retroactively.</p>
        </div>
      </div>
    </div>
  )
}
