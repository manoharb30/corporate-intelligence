import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { companyIntelligenceApi, CompanyIntelligenceData } from '../services/api'
import HistoricalContext from '../components/HistoricalContext'
import PersonSlideOver from '../components/PersonSlideOver'

function formatValue(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`
  return `$${v.toLocaleString()}`
}

function formatEventType(t: string): string {
  const map: Record<string, string> = {
    material_agreement: 'Material Agreement',
    executive_change: 'Executive Change',
    governance_change: 'Governance Change',
    acquisition_disposition: 'Acquisition / Disposition',
    control_change: 'Control Change',
    rights_modification: 'Rights Modification',
  }
  return map[t] || t
}

export default function CompanyIntelligence() {
  const { cik } = useParams<{ cik: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<CompanyIntelligenceData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedPerson, setSelectedPerson] = useState<string | null>(null)

  useEffect(() => {
    if (!cik) return
    let ignore = false
    setLoading(true)
    companyIntelligenceApi.get(cik)
      .then(res => { if (!ignore) setData(res.data) })
      .catch(() => {})
      .finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [cik])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full"></div>
      </div>
    )
  }

  if (!data) {
    return <div className="text-center py-24 text-gray-500">Company not found</div>
  }

  const { company, clusters, events, activist_filings, transactions, alerts, volume, officers, directors, cross_company_insiders } = data
  const buyClusters = clusters.filter(c => c.direction === 'buy')
  const sellClusters = clusters.filter(c => c.direction === 'sell')
  const hasCrossCompany = (name: string) => cross_company_insiders && name in cross_company_insiders && cross_company_insiders[name].length > 0

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <section className="py-6 mb-4">
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-3xl font-extrabold text-gray-900">{company.name}</h1>
          {company.ticker && <span className="text-xl text-gray-400">({company.ticker})</span>}
        </div>
        <div className="flex items-center gap-4 text-sm text-gray-500">
          {company.sic_description && <span>{company.sic_description}</span>}
          {company.state && <><span className="text-gray-300">|</span><span>{company.state}</span></>}
          <span className="text-gray-300">|</span>
          <span className="font-mono text-xs">CIK: {company.cik}</span>
        </div>
      </section>

      {/* Active Cluster Signals */}
      {clusters.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-bold text-gray-900 mb-3">Active Insider Signals</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {clusters.map((cl, idx) => {
              const isSell = cl.direction === 'sell'
              return (
                <div
                  key={`cluster-${idx}`}
                  onClick={() => navigate(`/signal/${encodeURIComponent(cl.accession_number)}`)}
                  className={`rounded-xl border p-4 cursor-pointer transition-colors ${
                    isSell
                      ? 'bg-red-50 border-red-200 hover:bg-red-100'
                      : 'bg-green-50 border-green-200 hover:bg-green-100'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                        isSell ? 'bg-red-600 text-white' : 'bg-green-600 text-white'
                      }`}>
                        {isSell ? 'SELL CLUSTER' : 'BUY CLUSTER'}
                      </span>
                      {!isSell && cl.conviction_tier === 'strong_buy' && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-green-800 text-white">
                          75% HIT RATE
                        </span>
                      )}
                      {!isSell && cl.conviction_tier === 'buy' && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 border border-green-300">
                          BUY
                        </span>
                      )}
                      {!isSell && cl.conviction_tier === 'watch' && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 border border-gray-300">
                          WATCH
                        </span>
                      )}
                    </div>
                    <span className={`text-xs font-medium uppercase ${
                      cl.signal_level === 'high' ? 'text-red-600' : 'text-yellow-600'
                    }`}>
                      {cl.signal_level}
                    </span>
                  </div>
                  <p className="text-sm font-semibold text-gray-900 mb-1">
                    {cl.num_insiders} insiders {isSell ? 'selling' : 'buying'} — {formatValue(cl.total_value)}
                  </p>
                  <p className="text-xs text-gray-500">{cl.signal_summary}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {cl.buyers.slice(0, 4).map((b, i) => {
                      const isCross = hasCrossCompany(b.name)
                      return isCross ? (
                        <button
                          key={i}
                          onClick={(e) => { e.stopPropagation(); setSelectedPerson(b.name) }}
                          className="text-xs bg-white px-2 py-0.5 rounded border border-purple-300 text-purple-700 hover:bg-purple-50 transition-colors cursor-pointer"
                        >
                          {b.name.split(' ').slice(0, 2).join(' ')}
                          {b.title ? ` (${b.title.slice(0, 20)})` : ''}
                          <span className="ml-1 text-purple-400">&#x2197;</span>
                        </button>
                      ) : (
                        <span key={i} className="text-xs text-gray-600 bg-white px-2 py-0.5 rounded border border-gray-200">
                          {b.name.split(' ').slice(0, 2).join(' ')}
                          {b.title ? ` (${b.title.slice(0, 20)})` : ''}
                        </span>
                      )
                    })}
                    {cl.buyers.length > 4 && (
                      <span className="text-xs text-gray-400">+{cl.buyers.length - 4} more</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* 8-K Events */}
      {events.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-bold text-gray-900 mb-3">Recent 8-K Events</h2>
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Date</th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Item</th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Type</th>
                  <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Signal</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e, idx) => (
                  <tr
                    key={`event-${idx}`}
                    onClick={() => navigate(`/signal/${encodeURIComponent(e.accession)}`)}
                    className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                  >
                    <td className="px-4 py-2 text-gray-600 font-mono text-xs">{e.date}</td>
                    <td className="px-4 py-2 font-medium text-gray-800">Item {e.item}</td>
                    <td className="px-4 py-2 text-gray-700">{formatEventType(e.type)}</td>
                    <td className="px-4 py-2 text-right">
                      {e.is_ma && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs font-medium">MA Signal</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* 13D Activist Filings */}
      {activist_filings.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-bold text-gray-900 mb-3">13D Activist Filings</h2>
          <div className="space-y-2">
            {activist_filings.map((af, idx) => (
              <div key={`activist-${idx}`} className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-gray-900">{af.filer}</span>
                    {af.percentage && <span className="ml-2 text-amber-700 font-bold">{af.percentage}% stake</span>}
                  </div>
                  <span className="text-xs text-gray-500">{af.date} · {af.form_type}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Insider Activity Summary + Transactions */}
      <section className="mb-8">
        <h2 className="text-lg font-bold text-gray-900 mb-3">Insider Activity</h2>

        {/* Volume summary bar */}
        {volume && volume.total_txns > 0 && (
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 mb-4">
            <div className="flex items-center justify-between text-sm">
              <div>
                <span className="text-gray-500">12-month activity:</span>
                <span className="ml-2 font-semibold text-gray-900">{volume.total_txns} trades</span>
                <span className="ml-1 text-gray-400">by {volume.distinct_insiders} insiders</span>
              </div>
              <div className="flex items-center gap-4">
                <div>
                  <span className="text-green-600 font-semibold">Buying: {formatValue(volume.total_buying)}</span>
                </div>
                <div>
                  <span className="text-red-600 font-semibold">Selling: {formatValue(volume.total_selling)}</span>
                </div>
              </div>
            </div>
            {/* Visual bar */}
            {(volume.total_buying > 0 || volume.total_selling > 0) && (
              <div className="mt-2 flex h-2 rounded-full overflow-hidden bg-gray-200">
                <div
                  className="bg-green-500"
                  style={{ width: `${(volume.total_buying / (volume.total_buying + volume.total_selling)) * 100}%` }}
                />
                <div
                  className="bg-red-500"
                  style={{ width: `${(volume.total_selling / (volume.total_buying + volume.total_selling)) * 100}%` }}
                />
              </div>
            )}
          </div>
        )}

        {/* Transaction table */}
        {transactions.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Date</th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Insider</th>
                  <th className="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Type</th>
                  <th className="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Value</th>
                </tr>
              </thead>
              <tbody>
                {transactions.slice(0, 15).map((t, idx) => (
                  <tr key={`txn-${idx}`} className="border-b border-gray-50">
                    <td className="px-4 py-2 text-gray-600 font-mono text-xs">{t.date}</td>
                    <td className="px-4 py-2">
                      {t.has_cross_company ? (
                        <button
                          onClick={() => setSelectedPerson(t.name)}
                          className="font-medium text-purple-700 hover:text-purple-900 hover:underline cursor-pointer"
                        >
                          {t.name} <span className="text-purple-400 text-xs">&#x2197;</span>
                        </button>
                      ) : (
                        <span className="font-medium text-gray-900">{t.name}</span>
                      )}
                      {t.title && <span className="ml-2 text-xs text-gray-400">{t.title}</span>}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        t.code === 'BUY' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {t.code}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right font-medium text-gray-800">
                      {t.value ? formatValue(t.value) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {transactions.length > 15 && (
              <div className="px-4 py-2 text-xs text-gray-400 border-t border-gray-100">
                Showing 15 of {transactions.length} transactions
              </div>
            )}
          </div>
        )}

        {transactions.length === 0 && (
          <p className="text-sm text-gray-400">No open-market insider transactions found</p>
        )}
      </section>

      {/* Alert History */}
      {alerts.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-bold text-gray-900 mb-3">Signal History</h2>
          <div className="space-y-2">
            {alerts.map((a, idx) => {
              const typeLabel =
                a.type === 'insider_cluster' ? 'Buy Cluster' :
                a.type === 'insider_sell_cluster' ? 'Sell Cluster' :
                a.type === 'activist_filing' ? '13D Filing' :
                a.type === 'large_purchase' ? 'Large Purchase' : a.type
              return (
                <div
                  key={`alert-${idx}`}
                  onClick={() => a.signal_id ? navigate(`/signal/${encodeURIComponent(a.signal_id)}`) : null}
                  className={`flex items-center justify-between bg-white border border-gray-200 rounded-lg px-4 py-2.5 ${
                    a.signal_id ? 'cursor-pointer hover:bg-gray-50' : ''
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${
                      a.severity === 'high' ? 'bg-red-100 text-red-700' :
                      a.severity === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {a.severity}
                    </span>
                    <span className="text-sm text-gray-700">{typeLabel}</span>
                  </div>
                  <span className="text-xs text-gray-400">{a.date}</span>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Officers & Directors */}
      {(officers.length > 0 || directors.length > 0) && (
        <section className="mb-8">
          <h2 className="text-lg font-bold text-gray-900 mb-3">Officers & Directors</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {officers.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">Officers</h3>
                <div className="space-y-1">
                  {officers.map((o, i) => (
                    <div key={i} className="text-sm">
                      <span className="font-medium text-gray-900">{o.name}</span>
                      {o.title && <span className="ml-2 text-gray-400">{o.title}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {directors.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">Directors</h3>
                <div className="space-y-1">
                  {directors.map((d, i) => (
                    <div key={i} className="text-sm font-medium text-gray-900">{d.name}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {/* No data state */}
      {clusters.length === 0 && events.length === 0 && transactions.length === 0 && alerts.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg font-semibold mb-1">No intelligence data available</p>
          <p className="text-sm">We don't have insider trading or event data for this company yet.</p>
        </div>
      )}

      {/* Person slide-over */}
      <PersonSlideOver
        personName={selectedPerson}
        onClose={() => setSelectedPerson(null)}
      />
    </div>
  )
}
