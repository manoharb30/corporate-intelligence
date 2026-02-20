import { DecisionCard as DecisionCardType } from '../services/api'

interface DecisionCardProps {
  card: DecisionCardType
}

const actionStyles: Record<string, { bg: string; text: string; border: string }> = {
  BUY: { bg: 'bg-green-600', text: 'text-white', border: 'border-green-500' },
  WATCH: { bg: 'bg-yellow-500', text: 'text-white', border: 'border-yellow-400' },
  PASS: { bg: 'bg-gray-500', text: 'text-white', border: 'border-gray-400' },
}

const convictionLabel: Record<string, string> = {
  HIGH: 'High conviction',
  MEDIUM: 'Medium conviction',
  LOW: 'Low conviction',
}

const directionStyles: Record<string, { badge: string; label: string }> = {
  buying: { badge: 'bg-green-100 text-green-800 border-green-200', label: 'NET BUYING' },
  selling: { badge: 'bg-red-100 text-red-800 border-red-200', label: 'NET SELLING' },
  mixed: { badge: 'bg-gray-100 text-gray-700 border-gray-200', label: 'MIXED' },
  none: { badge: 'bg-gray-100 text-gray-500 border-gray-200', label: 'NO TRADES' },
}

function formatDays(days: number | null): string {
  if (days === null) return ''
  if (days === 0) return 'Filed today'
  if (days === 1) return 'Filed 1d ago'
  if (days < 30) return `Filed ${days}d ago`
  if (days < 365) return `Filed ${Math.round(days / 30)}mo ago`
  return `Filed ${(days / 365).toFixed(1)}y ago`
}

export default function DecisionCard({ card }: DecisionCardProps) {
  const style = actionStyles[card.action] || actionStyles.PASS
  const dir = directionStyles[card.insider_direction] || directionStyles.none
  const hasPriceData = card.price_change_pct !== undefined && card.price_change_pct !== null
  const priceUp = hasPriceData && card.price_change_pct! >= 0

  return (
    <div className={`rounded-xl border-2 ${style.border} overflow-hidden shadow-lg mb-6`}>
      {/* Top bar: Action + Conviction + Filed */}
      <div className={`${style.bg} ${style.text} px-6 py-4 flex items-center justify-between`}>
        <div className="flex items-center gap-4">
          <span className="text-3xl font-black tracking-tight">{card.action}</span>
          <span className="text-sm font-medium opacity-90">{convictionLabel[card.conviction] || card.conviction}</span>
        </div>
        {card.days_since_filing !== null && (
          <span className="text-sm font-medium opacity-80">{formatDays(card.days_since_filing)}</span>
        )}
      </div>

      {/* Body */}
      <div className="bg-white px-6 py-4">
        {/* One-liner */}
        <p className="text-gray-800 font-medium text-lg mb-3">{card.one_liner}</p>

        {/* Price change + Insider direction */}
        <div className="flex items-center gap-4 flex-wrap">
          {hasPriceData && (
            <div className="flex items-center gap-2">
              <span className={`text-lg font-bold ${priceUp ? 'text-green-600' : 'text-red-600'}`}>
                {priceUp ? '\u25B2' : '\u25BC'} {priceUp ? '+' : ''}{card.price_change_pct}%
              </span>
              <span className="text-sm text-gray-500">since filing</span>
              {card.price_at_filing !== undefined && card.price_current !== undefined && (
                <span className="text-xs text-gray-400">
                  ${card.price_at_filing.toFixed(2)} &rarr; ${card.price_current.toFixed(2)}
                </span>
              )}
            </div>
          )}

          <span className={`px-3 py-1 rounded-full text-xs font-bold border ${dir.badge}`}>
            Insiders: {dir.label}
          </span>
        </div>
      </div>
    </div>
  )
}
