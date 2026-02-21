import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { accuracyApi, ProofHit } from '../services/api'

interface ProofWallProps {
  variant: 'dark' | 'light'
}

function formatValue(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`
  return `$${value.toFixed(0)}`
}

export default function ProofWall({ variant }: ProofWallProps) {
  const [hits, setHits] = useState<ProofHit[]>([])
  const [totalHits, setTotalHits] = useState<number | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        const [topRes, fullRes] = await Promise.allSettled([
          accuracyApi.getTopHits(3),
          accuracyApi.getTopHits(10),
        ])
        if (topRes.status === 'fulfilled') setHits(topRes.value.data)
        if (fullRes.status === 'fulfilled') setTotalHits(fullRes.value.data.length)
      } catch {
        // graceful degradation — render nothing
      }
    }
    load()
  }, [])

  if (hits.length === 0) return null

  const isDark = variant === 'dark'

  return (
    <section className={isDark ? 'mb-14' : 'mb-16'}>
      <div className={`rounded-xl p-8 ${isDark ? 'bg-gradient-to-r from-gray-900 to-primary-900 text-white' : 'bg-white border border-gray-200 shadow-sm'}`}>

        {/* Header */}
        <div className="mb-6">
          <h3 className={`text-xl font-bold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
            Real Signals. Real Returns.
          </h3>
          <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
            Every result below is verifiable in SEC filings
          </p>
        </div>

        {/* Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {hits.map((hit) => {
            const signalUrl = `/signal/CLUSTER-${hit.cik}-${hit.signal_date}`
            return (
              <Link
                key={`${hit.cik}-${hit.signal_date}`}
                to={signalUrl}
                className={`block rounded-lg p-5 transition-colors ${
                  isDark
                    ? 'bg-white/10 hover:bg-white/15 border border-white/10'
                    : 'bg-gray-50 hover:bg-gray-100 border border-gray-200'
                }`}
              >
                {/* Signal level badge */}
                <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold uppercase mb-3 ${
                  hit.signal_level === 'high'
                    ? 'bg-red-600 text-white'
                    : hit.signal_level === 'medium'
                    ? 'bg-yellow-500 text-white'
                    : 'bg-gray-500 text-white'
                }`}>
                  {hit.signal_level}
                </span>

                {/* Company */}
                <div className={`font-semibold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                  {hit.company_name}
                  {hit.ticker && <span className={`ml-1 font-normal ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>({hit.ticker})</span>}
                </div>

                {/* Insider stats */}
                <div className={`text-sm mb-3 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                  {hit.num_buyers} insider{hit.num_buyers !== 1 ? 's' : ''} bought {formatValue(hit.total_buy_value)}
                </div>

                {/* Return */}
                {hit.best_price_change !== null && (
                  <div className="mb-3">
                    <span className="text-2xl font-bold text-green-400">
                      +{hit.best_price_change.toFixed(1)}%
                    </span>
                    {hit.best_horizon && (
                      <span className={`text-sm ml-1 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                        in {hit.best_horizon.replace('d', ' days')}
                      </span>
                    )}
                  </div>
                )}

                {/* 8-K confirmation */}
                {hit.followed_by_8k && hit.days_to_first_8k !== null && (
                  <div className={`text-xs mb-3 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    8-K filed {hit.days_to_first_8k}d later
                  </div>
                )}

                {/* CTA */}
                <div className={`text-sm font-medium ${isDark ? 'text-primary-400' : 'text-primary-600'}`}>
                  See story &rarr;
                </div>
              </Link>
            )
          })}
        </div>

        {/* Footer link */}
        {totalHits !== null && totalHits > 3 && (
          <div className="text-center">
            <Link
              to="/accuracy"
              className={`text-sm font-medium hover:underline ${isDark ? 'text-gray-300 hover:text-white' : 'text-gray-600 hover:text-gray-900'}`}
            >
              See all {totalHits}+ verified hits in our Track Record &rarr;
            </Link>
          </div>
        )}
      </div>
    </section>
  )
}
