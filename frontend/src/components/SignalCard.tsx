import { Link } from 'react-router-dom'
import { SignalItem } from '../services/api'

interface SignalCardProps {
  signal: SignalItem
  compact?: boolean
}

const badgeClass: Record<string, string> = {
  critical: 'bg-purple-600 text-white animate-pulse',
  high_bearish: 'bg-red-700 text-white',
  high: 'bg-red-500 text-white',
  medium: 'bg-yellow-500 text-white',
  low: 'bg-blue-500 text-white',
}

const badgeLabel: Record<string, string> = {
  critical: 'CRITICAL',
  high_bearish: 'HIGH BEARISH',
  high: 'HIGH',
  medium: 'MEDIUM',
  low: 'LOW',
}

function formatValue(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`
  if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}K`
  return `$${val.toFixed(0)}`
}

export default function SignalCard({ signal, compact = false }: SignalCardProps) {
  const level = signal.combined_signal_level || signal.signal_level
  const insiderDir = signal.insider_context?.net_direction
  const buyType = signal.insider_context?.near_filing_buy_type
  const isCluster = signal.signal_type === 'insider_cluster'
  const isSellCluster = signal.signal_type === 'insider_sell_cluster'
  const isCompound = signal.signal_type === 'compound'
  const isAnyCluster = isCluster || isSellCluster
  const buyers = signal.cluster_detail?.buyers || []
  const notableTrades = signal.insider_context?.notable_trades || []
  const convictionTier = signal.conviction_tier

  return (
    <Link
      to={`/signal/${encodeURIComponent(signal.accession_number)}`}
      className="block bg-white rounded-lg border border-gray-200 hover:border-primary-300 hover:shadow-md transition-all p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${badgeClass[level] || badgeClass.low}`}>
              {badgeLabel[level] || level}
            </span>
            {isCluster && (
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-600 text-white">
                OPEN MARKET CLUSTER
              </span>
            )}
            {convictionTier === 'strong_buy' && (
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-green-800 text-white">
                STRONG BUY · 75%
              </span>
            )}
            {convictionTier === 'buy' && (
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 border border-green-300">
                BUY
              </span>
            )}
            {convictionTier === 'watch' && (
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600 border border-gray-200">
                WATCH
              </span>
            )}
            {isSellCluster && (
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-600 text-white">
                SELL CLUSTER
              </span>
            )}
            {isCompound && (
              <span className="px-2 py-0.5 rounded text-xs font-bold bg-purple-700 text-white">
                COMPOUND
              </span>
            )}
            {insiderDir && insiderDir !== 'none' && !isAnyCluster && !isCompound && (
              <span className={`px-2 py-0.5 rounded text-xs font-medium border ${
                insiderDir === 'buying' ? 'text-green-700 bg-green-50 border-green-200' :
                insiderDir === 'selling' ? 'text-red-700 bg-red-50 border-red-200' :
                'text-gray-600 bg-gray-50 border-gray-200'
              }`}>
                {insiderDir === 'buying'
                  ? buyType === 'open_market' ? 'Open Market Buying'
                    : buyType === 'exercise_hold' ? 'Exercise & Hold'
                    : buyType === 'mixed' ? 'Open Market + Exercise'
                    : 'Insiders Buying'
                  : insiderDir === 'selling' ? 'Insiders Selling' : 'Mixed Trading'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-gray-900 truncate">{signal.company_name}</span>
            {signal.ticker && (
              <span className="text-sm text-gray-500 shrink-0">({signal.ticker})</span>
            )}
          </div>
          {!compact && (
            <>
              {/* Cluster: show who bought/sold and at what price */}
              {isAnyCluster && buyers.length > 0 ? (
                <div className="mt-1 space-y-0.5">
                  {buyers.slice(0, 3).map((b, i) => (
                    <div key={i} className="text-xs text-gray-600">
                      <span className="font-medium text-gray-800">{b.title || b.name}</span>
                      {isSellCluster ? ' sold ' : ' bought '}
                      <span className={`font-medium ${isSellCluster ? 'text-red-700' : 'text-green-700'}`}>{formatValue(b.total_value)}</span>
                      {b.avg_price_per_share && (
                        <span className="text-gray-400"> @ ${b.avg_price_per_share.toFixed(2)}/share</span>
                      )}
                    </div>
                  ))}
                  {buyers.length > 3 && (
                    <div className="text-xs text-gray-400">+{buyers.length - 3} more</div>
                  )}
                </div>
              ) : !isAnyCluster && notableTrades.length > 0 ? (
                /* 8-K: show notable insider trades near filing */
                <div className="mt-1 space-y-0.5">
                  {notableTrades.slice(0, 2).map((t, i) => (
                    <div key={i} className="text-xs text-gray-600">{t}</div>
                  ))}
                  {notableTrades.length > 2 && (
                    <div className="text-xs text-gray-400">+{notableTrades.length - 2} more trades</div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-600 line-clamp-2">{signal.signal_summary}</p>
              )}
            </>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs text-gray-400 font-mono">{signal.filing_date}</p>
          {!compact && (
            <div className="flex flex-wrap gap-1 mt-1 justify-end">
              {isCompound ? (
                <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-purple-50 border border-purple-200 text-purple-700">
                  Multi-Source
                </span>
              ) : isAnyCluster && signal.cluster_detail ? (
                <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                  isSellCluster
                    ? 'bg-red-50 border border-red-200 text-red-700'
                    : 'bg-emerald-50 border border-emerald-200 text-emerald-700'
                }`}>
                  {signal.cluster_detail.num_buyers} {isSellCluster ? 'sellers' : 'buyers'}
                </span>
              ) : (
                signal.items.slice(0, 3).map(item => (
                  <span key={item} className="px-1.5 py-0.5 bg-gray-100 rounded text-xs font-mono text-gray-600">
                    {item}
                  </span>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </Link>
  )
}
