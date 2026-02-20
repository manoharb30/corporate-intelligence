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

export default function SignalCard({ signal, compact = false }: SignalCardProps) {
  const level = signal.combined_signal_level || signal.signal_level
  const insiderDir = signal.insider_context?.net_direction
  const isCluster = signal.signal_type === 'insider_cluster'

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
                INSIDER CLUSTER
              </span>
            )}
            {insiderDir && insiderDir !== 'none' && !isCluster && (
              <span className={`px-2 py-0.5 rounded text-xs font-medium border ${
                insiderDir === 'buying' ? 'text-green-700 bg-green-50 border-green-200' :
                insiderDir === 'selling' ? 'text-red-700 bg-red-50 border-red-200' :
                'text-gray-600 bg-gray-50 border-gray-200'
              }`}>
                {insiderDir === 'buying' ? 'Insiders Buying' :
                 insiderDir === 'selling' ? 'Insiders Selling' : 'Mixed Trading'}
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
            <p className="text-sm text-gray-600 line-clamp-2">{signal.signal_summary}</p>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs text-gray-400 font-mono">{signal.filing_date}</p>
          {!compact && (
            <div className="flex flex-wrap gap-1 mt-1 justify-end">
              {isCluster && signal.cluster_detail ? (
                <span className="px-1.5 py-0.5 bg-emerald-50 border border-emerald-200 rounded text-xs text-emerald-700 font-medium">
                  {signal.cluster_detail.num_buyers} insiders buying
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
