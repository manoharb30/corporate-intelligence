import { useEffect, useState } from 'react'
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

function PnlText({ value, pct, className = '' }: { value: number; pct?: number | null; className?: string }) {
  const up = value >= 0
  return (
    <span className={`${up ? 'text-green-600' : 'text-red-600'} ${className}`}>
      {up ? '+' : ''}{fmtUsd(value)}{pct != null && ` (${up ? '+' : ''}${pct.toFixed(2)}%)`}
    </span>
  )
}

function EquityCurve({ curve }: { curve: { date: string; equity: number }[] }) {
  if (curve.length < 2) {
    return (
      <div className="text-center text-gray-500 text-sm py-10">
        Equity curve appears after the first two trading days.
      </div>
    )
  }
  const W = 920, H = 240, L = 60, R = 20, T = 14, B = 30
  const plotW = W - L - R, plotH = H - T - B
  const values = curve.map((c) => c.equity)
  const pad = Math.max((Math.max(...values) - Math.min(...values)) * 0.15, 50)
  const yMin = Math.min(...values) - pad
  const yMax = Math.max(...values) + pad
  const x = (i: number) => L + (i / (curve.length - 1)) * plotW
  const y = (v: number) => T + (1 - (v - yMin) / (yMax - yMin)) * plotH
  const path = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')
  const area = `${path} L ${x(values.length - 1)} ${y(yMin)} L ${x(0)} ${y(yMin)} Z`
  const gridLines = 4
  const labelIdx = [0, Math.floor((curve.length - 1) / 2), curve.length - 1]
  const last = values[values.length - 1]

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
      aria-label={`Equity curve from ${curve[0].date} to ${curve[curve.length - 1].date}`}>
      {Array.from({ length: gridLines + 1 }, (_, i) => {
        const v = yMin + ((yMax - yMin) * i) / gridLines
        return (
          <g key={i}>
            <line x1={L} y1={y(v)} x2={L + plotW} y2={y(v)} stroke="#e5e7eb" strokeWidth={1} />
            <text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize={11} fill="#9ca3af">
              {(v / 1000).toFixed(yMax - yMin < 2000 ? 2 : 1)}K
            </text>
          </g>
        )
      })}
      {labelIdx.map((i) => (
        <text key={i} x={x(i)} y={H - 8} textAnchor="middle" fontSize={11} fill="#9ca3af">
          {fmtDate(curve[i].date)}
        </text>
      ))}
      <path d={area} fill="#0078f8" opacity={0.08} />
      <path d={path} fill="none" stroke="#0078f8" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(values.length - 1)} cy={y(last)} r={4.5} fill="#0078f8" stroke="#fff" strokeWidth={2} />
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
  const activities = snap.activities ?? []

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
        Alpaca paper account · {fmtUsd(acct.initial_capital, 0)} initial · as of {new Date(snap.as_of!).toLocaleString()}
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
            {positions.length} open position{positions.length === 1 ? '' : 's'}
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1">SGOV cash sweep</div>
          <div className="text-2xl font-bold text-gray-900 tabular-nums">{fmtUsd(snap.sweep?.market_value ?? 0)}</div>
          <div className="text-xs mt-1 text-gray-500 tabular-nums">
            {snap.sweep ? `${snap.sweep.qty.toLocaleString()} sh` : 'no sweep position yet'}
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Free cash</div>
          <div className="text-2xl font-bold text-gray-900 tabular-nums">{fmtUsd(acct.cash)}</div>
          <div className="text-xs mt-1 text-gray-500">funds new $5K signal slices</div>
        </div>
      </div>

      {/* Allocation */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-4">
        <div className="px-5 py-3.5 border-b border-gray-200 flex flex-wrap items-center gap-3">
          <h2 className="text-sm font-bold text-gray-900">Allocation</h2>
          <span className="text-xs text-gray-400 tabular-nums">
            20 position slots · {positions.length} filled
          </span>
        </div>
        <div className="p-5">
          <div className="flex gap-0.5 h-3.5 rounded-full overflow-hidden" role="img"
            aria-label={`Allocation: signal positions ${alloc.positions_pct}%, SGOV sweep ${alloc.sweep_pct}%, cash ${alloc.cash_pct}%`}>
            <div className="bg-blue-600" style={{ width: `${alloc.positions_pct}%` }} />
            <div className="bg-blue-300" style={{ width: `${alloc.sweep_pct}%` }} />
            <div className="bg-gray-300" style={{ width: `${alloc.cash_pct}%` }} />
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 mt-2.5 text-xs text-gray-500 tabular-nums">
            <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-blue-600 mr-1.5 align-[-1px]" />Signal positions · {alloc.positions_pct}%</span>
            <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-blue-300 mr-1.5 align-[-1px]" />SGOV sweep · {alloc.sweep_pct}%</span>
            <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-gray-300 mr-1.5 align-[-1px]" />Cash · {alloc.cash_pct}%</span>
          </div>
        </div>
      </div>

      {/* Equity curve */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-4">
        <div className="px-5 py-3.5 border-b border-gray-200">
          <h2 className="text-sm font-bold text-gray-900">Equity curve <span className="font-normal text-xs text-gray-400 ml-2">daily close</span></h2>
        </div>
        <div className="p-5">
          <EquityCurve curve={snap.equity_curve ?? []} />
        </div>
      </div>

      {/* Open positions */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-4">
        <div className="px-5 py-3.5 border-b border-gray-200 flex flex-wrap items-center gap-3">
          <h2 className="text-sm font-bold text-gray-900">Open positions</h2>
          <span className="text-xs text-gray-400 tabular-nums">
            {snap.avg_shortfall_pct != null && `on average we bought ${Math.abs(snap.avg_shortfall_pct)}% ${snap.avg_shortfall_pct >= 0 ? 'above' : 'below'} the signal-day price · `}
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
                  <th className="text-right px-4 py-2.5">Buy vs signal</th>
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
                      <div className="font-bold text-gray-900">{p.ticker}</div>
                      {p.company_name && <div className="text-xs text-gray-500">{p.company_name}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <div>{fmtDate(p.signal_date)}</div>
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
                        <span className={`text-[11px] font-semibold rounded-full px-2 py-0.5 ${p.shortfall_pct > 0 ? 'bg-amber-50 text-amber-700' : 'bg-green-50 text-green-700'}`}>
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

      {/* Activity */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-6">
        <div className="px-5 py-3.5 border-b border-gray-200">
          <h2 className="text-sm font-bold text-gray-900">Activity <span className="font-normal text-xs text-gray-400 ml-2">order fills</span></h2>
        </div>
        {activities.length === 0 ? (
          <div className="text-center text-gray-500 text-sm py-8">No activity yet.</div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {activities.slice(0, 20).map((a, i) => (
              <li key={i} className="flex gap-3 px-5 py-2.5 text-sm items-start">
                <span className="text-xs text-gray-400 w-32 flex-shrink-0 tabular-nums">
                  {a.time ? new Date(a.time).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                </span>
                <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${a.type === 'sweep' ? 'bg-blue-300' : 'bg-blue-600'}`} />
                <span className="tabular-nums">
                  <span className="font-semibold">{a.side.toUpperCase()} {a.qty.toLocaleString()} {a.symbol}</span>
                  <span className="text-gray-500"> @ {fmtUsd(a.price)}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="text-xs text-gray-400 leading-relaxed">
        <span className="font-semibold text-gray-500">How this works:</span> every strong_buy signal gets a fixed
        $5,000 investment, bought in 3 slices spread across the signal day (cash comes out of the SGOV reserve).
        We show the stock's price on signal day next to the price we actually paid — "Buy vs signal" — so the
        portfolio's results stay honestly comparable to the published signal statistics. Each position is sold
        90 days after its signal, in 3 slices the same way it was bought. Idle cash sits in SGOV, a US Treasury
        ETF, earning ~4–5% instead of sitting still.
      </p>
    </div>
  )
}
