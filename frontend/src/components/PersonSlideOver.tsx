/**
 * PersonSlideOver — slide-over panel showing a person's cross-company trading activity.
 *
 * Opens from the right when a user clicks an insider name anywhere in the app.
 * Shows all companies they trade at, transaction history, roles, and net direction.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { personIntelligenceApi, PersonIntelligenceData } from '../services/api'

function formatValue(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`
  return `$${v.toLocaleString()}`
}

interface PersonSlideOverProps {
  personName: string | null
  onClose: () => void
}

export default function PersonSlideOver({ personName, onClose }: PersonSlideOverProps) {
  const navigate = useNavigate()
  const [data, setData] = useState<PersonIntelligenceData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!personName) {
      setData(null)
      return
    }
    let ignore = false
    setLoading(true)
    setData(null)
    personIntelligenceApi.get(personName)
      .then(res => { if (!ignore) setData(res.data) })
      .catch(() => {})
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [personName])

  if (!personName) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed inset-y-0 right-0 w-full max-w-md bg-white shadow-2xl z-50 overflow-y-auto transition-transform">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-5 py-4 flex items-center justify-between z-10">
          <div>
            <h2 className="text-lg font-bold text-gray-900">{personName}</h2>
            {data && (
              <p className="text-xs text-gray-500">
                {data.num_companies} {data.num_companies === 1 ? 'company' : 'companies'} · {data.total_trades} trades · {data.net_direction}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin h-8 w-8 border-4 border-primary-500 border-t-transparent rounded-full"></div>
          </div>
        )}

        {!loading && !data && (
          <div className="text-center py-16 text-gray-400">
            <p>No trading data found for this person.</p>
          </div>
        )}

        {data && (
          <div className="p-5 space-y-6">
            {/* Summary bar */}
            <div className="flex gap-3">
              <div className="flex-1 bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                <div className="text-lg font-black text-green-700">{formatValue(data.total_buying)}</div>
                <div className="text-xs text-green-600">Total buying</div>
              </div>
              <div className="flex-1 bg-red-50 border border-red-200 rounded-lg p-3 text-center">
                <div className="text-lg font-black text-red-700">{formatValue(data.total_selling)}</div>
                <div className="text-xs text-red-600">Total selling</div>
              </div>
            </div>

            {/* Companies */}
            <div>
              <h3 className="text-sm font-bold text-gray-900 mb-2">
                Active at {data.num_companies} {data.num_companies === 1 ? 'company' : 'companies'}
              </h3>
              <div className="space-y-2">
                {data.companies.map(c => {
                  const isBuying = c.total_buying > c.total_selling
                  const total = c.total_buying + c.total_selling
                  const trades = c.buy_count + c.sell_count
                  return (
                    <div
                      key={c.cik}
                      onClick={() => { navigate(`/company/${c.cik}`); onClose() }}
                      className={`rounded-lg border p-3 cursor-pointer transition-colors ${
                        isBuying
                          ? 'bg-green-50 border-green-200 hover:bg-green-100'
                          : 'bg-red-50 border-red-200 hover:bg-red-100'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-gray-900">{c.ticker || 'N/A'}</span>
                          <span className="text-xs text-gray-500 truncate max-w-[150px]">{c.name}</span>
                        </div>
                        <span className={`text-sm font-bold ${isBuying ? 'text-green-700' : 'text-red-700'}`}>
                          {formatValue(total)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>
                          {c.title && <span className="text-gray-600">{c.title} · </span>}
                          {trades} trades · {c.latest_trade}
                        </span>
                        <div className="flex gap-2">
                          {c.buy_count > 0 && <span className="text-green-600">{c.buy_count} buys</span>}
                          {c.sell_count > 0 && <span className="text-red-600">{c.sell_count} sells</span>}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Roles */}
            {data.roles.length > 0 && (
              <div>
                <h3 className="text-sm font-bold text-gray-900 mb-2">Roles</h3>
                <div className="flex flex-wrap gap-2">
                  {data.roles.map((r, i) => (
                    <span key={i} className="px-2.5 py-1 bg-gray-100 border border-gray-200 rounded-lg text-xs text-gray-700">
                      {r.role === 'officer' ? 'Officer' : 'Director'} at {r.ticker || r.name}
                      {r.title && ` — ${r.title}`}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Recent transactions */}
            <div>
              <h3 className="text-sm font-bold text-gray-900 mb-2">Recent Transactions</h3>
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-100">
                      <th className="text-left px-3 py-2 font-semibold text-gray-500 uppercase">Date</th>
                      <th className="text-left px-3 py-2 font-semibold text-gray-500 uppercase">Company</th>
                      <th className="text-left px-3 py-2 font-semibold text-gray-500 uppercase">Type</th>
                      <th className="text-right px-3 py-2 font-semibold text-gray-500 uppercase">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.transactions.slice(0, 20).map((t, i) => (
                      <tr key={i} className="border-b border-gray-50">
                        <td className="px-3 py-1.5 text-gray-600 font-mono">{t.date}</td>
                        <td className="px-3 py-1.5 font-medium text-gray-800">{t.ticker || 'N/A'}</td>
                        <td className="px-3 py-1.5">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            t.code === 'BUY' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                          }`}>
                            {t.code}
                          </span>
                        </td>
                        <td className="px-3 py-1.5 text-right font-medium text-gray-800">
                          {t.value ? formatValue(t.value) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data.transactions.length > 20 && (
                  <div className="px-3 py-1.5 text-[10px] text-gray-400 border-t border-gray-100">
                    Showing 20 of {data.total_trades} transactions
                  </div>
                )}
              </div>
            </div>

            {/* Cross-company callout */}
            {data.num_companies > 1 && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <svg className="w-4 h-4 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span className="text-xs font-bold text-purple-800">Cross-Company Activity</span>
                </div>
                <p className="text-xs text-purple-700">
                  This insider is actively trading at {data.num_companies} different companies.
                  {data.net_direction === 'net buyer' && ' Deploying capital across multiple positions — high conviction pattern.'}
                  {data.net_direction === 'net seller' && ' Liquidating across multiple positions.'}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
