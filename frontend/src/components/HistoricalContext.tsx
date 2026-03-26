/**
 * HistoricalContext — "What History Says" component.
 *
 * Shows how similar signals performed historically based on sector and direction.
 * Full card version for SignalStory, one-liner version for signal cards.
 */

// Pre-calculated stats from autoresearch (3 rounds, 80+ experiments)
const BUY_STATS: Record<string, SectorStats> = {
  "60": {
    total: 18, hits: 16, hit_rate: 88.9, avg_return: 7.4, avg_alpha: 2.24,
    description: "banking companies where multiple insiders bought in a coordinated window",
  },
  "73": {
    total: 19, hits: 13, hit_rate: 68.4, avg_return: 5.28, avg_alpha: 3.21,
    description: "technology companies where multiple insiders bought together",
  },
  "36": {
    total: 6, hits: 5, hit_rate: 83.3, avg_return: 6.08, avg_alpha: -0.46,
    description: "electronics companies where multiple insiders bought together",
  },
  "28": {
    total: 10, hits: 5, hit_rate: 50.0, avg_return: 12.0, avg_alpha: 10.42,
    description: "pharmaceutical companies where multiple insiders bought together",
  },
  "61": {
    total: 20, hits: 15, hit_rate: 75.0, avg_return: 8.91, avg_alpha: 4.04,
    description: "financial companies where multiple insiders bought together",
  },
  "62": {
    total: 20, hits: 15, hit_rate: 75.0, avg_return: 8.91, avg_alpha: 4.04,
    description: "financial companies where multiple insiders bought together",
  },
  "63": {
    total: 20, hits: 15, hit_rate: 75.0, avg_return: 8.91, avg_alpha: 4.04,
    description: "financial companies where multiple insiders bought together",
  },
  "65": {
    total: 20, hits: 15, hit_rate: 75.0, avg_return: 8.91, avg_alpha: 4.04,
    description: "financial companies where multiple insiders bought together",
  },
  "67": {
    total: 20, hits: 15, hit_rate: 75.0, avg_return: 8.91, avg_alpha: 4.04,
    description: "financial companies where multiple insiders bought together",
  },
  "all": {
    total: 142, hits: 96, hit_rate: 67.8, avg_return: 4.77, avg_alpha: 1.5,
    description: "companies where 3+ insiders bought in a coordinated window",
  },
}

const SELL_STATS: Record<string, SectorStats> = {
  "60": {
    total: 5, hits: 4, hit_rate: 80.0, avg_return: -2.01, avg_alpha: -7.4,
    description: "financial companies where multiple insiders sold together",
  },
  "73": {
    total: 50, hits: 36, hit_rate: 72.0, avg_return: -11.74, avg_alpha: -16.2,
    description: "technology companies where multiple insiders sold together",
  },
  "all": {
    total: 64, hits: 46, hit_rate: 71.9, avg_return: -3.5, avg_alpha: -3.0,
    description: "companies where multiple insiders sold in a coordinated window",
  },
}

interface SectorStats {
  total: number
  hits: number
  hit_rate: number
  avg_return: number
  avg_alpha?: number
  description: string
}

function getStats(sicCode: string | null | undefined, direction: 'buy' | 'sell'): SectorStats {
  const sic2 = sicCode ? sicCode.substring(0, 2) : ''
  const table = direction === 'sell' ? SELL_STATS : BUY_STATS
  return table[sic2] || table['all']
}

interface HistoricalContextProps {
  sicCode?: string | null
  direction: 'buy' | 'sell'
  variant?: 'card' | 'inline'
}

export default function HistoricalContext({ sicCode, direction, variant = 'card' }: HistoricalContextProps) {
  const stats = getStats(sicCode, direction)
  const isLimited = stats.total < 10
  const isSell = direction === 'sell'

  const verb = isSell ? 'dropped' : 'went up'
  const signalType = isSell ? 'sell signals' : 'similar signals'

  if (variant === 'inline') {
    return (
      <span className="text-xs text-gray-400">
        History: {stats.hits}/{stats.total} similar signals {verb} ({stats.hit_rate}%)
        {' · '}Avg {stats.avg_return >= 0 ? '+' : ''}{stats.avg_return}% in 90d
        {isLimited && ' · limited data'}
      </span>
    )
  }

  return (
    <div className={`rounded-xl p-5 mb-4 ${isSell ? 'bg-red-50 border border-red-100' : 'bg-blue-50 border border-blue-100'}`}>
      <div className="flex items-center gap-2 mb-2">
        <svg className={`w-4 h-4 ${isSell ? 'text-red-400' : 'text-blue-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 className="text-sm font-bold text-gray-900">What History Says</h3>
      </div>
      <p className="text-sm text-gray-700 leading-relaxed">
        We found <span className="font-semibold">{stats.total}</span> {signalType} in {stats.description}.{' '}
        <span className="font-semibold">{stats.hits} out of {stats.total}</span> {verb} ({stats.hit_rate}%),
        averaging <span className="font-semibold">{stats.avg_return >= 0 ? '+' : ''}{stats.avg_return}%</span> return
        within 90 days.
      </p>
      {isLimited && (
        <p className="text-xs text-gray-400 mt-2">
          (limited data — fewer than 10 historical signals)
        </p>
      )}
      <p className="text-xs text-gray-400 mt-2">
        Based on {stats.total} similar signals since March 2024
      </p>
    </div>
  )
}

export { getStats }
export type { SectorStats }
