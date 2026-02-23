import { DecisionCard as DecisionCardType } from '../services/api'

interface DecisionCardProps {
  card: DecisionCardType
  isCluster?: boolean
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

function buyTypeLabel(buyType?: string): string {
  if (buyType === 'open_market') return ' (Open Market)'
  if (buyType === 'exercise_hold') return ' (Exercise & Hold)'
  if (buyType === 'mixed') return ' (Open Market + Exercise)'
  return ''
}

function formatDays(days: number | null, isCluster: boolean): string {
  if (days === null) return ''
  const prefix = isCluster ? 'Detected' : 'Filed'
  if (days === 0) return `${prefix} today`
  if (days === 1) return `${prefix} 1d ago`
  if (days < 30) return `${prefix} ${days}d ago`
  if (days < 365) return `${prefix} ${Math.round(days / 30)}mo ago`
  return `${prefix} ${(days / 365).toFixed(1)}y ago`
}

const tierStyles: Record<string, { bg: string; text: string; dot: string }> = {
  Strong: { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },
  Moderate: { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500' },
  Weak: { bg: 'bg-gray-50', text: 'text-gray-600', dot: 'bg-gray-400' },
}

export default function DecisionCard({ card, isCluster = false }: DecisionCardProps) {
  const style = actionStyles[card.action] || actionStyles.PASS
  const dir = directionStyles[card.insider_direction] || directionStyles.none
  const hasPriceData = card.price_change_pct !== undefined && card.price_change_pct !== null
  const priceUp = hasPriceData && card.price_change_pct! >= 0
  const conf = card.confidence
  const tier = conf ? tierStyles[conf.tier] || tierStyles.Weak : null

  return (
    <div className={`rounded-xl border-2 ${style.border} overflow-hidden shadow-lg mb-6`}>
      {/* Top bar: Action + Conviction + Filed */}
      <div className={`${style.bg} ${style.text} px-6 py-4 flex items-center justify-between`}>
        <div className="flex items-center gap-4">
          <span className="text-3xl font-black tracking-tight">{card.action}</span>
          <span className="text-sm font-medium opacity-90">{convictionLabel[card.conviction] || card.conviction}</span>
        </div>
        {card.days_since_filing !== null && (
          <span className="text-sm font-medium opacity-80">{formatDays(card.days_since_filing, isCluster)}</span>
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
              <span className="text-sm text-gray-500">{card.price_label || (isCluster ? 'since first trade' : 'since filing')}</span>
              {card.price_at_filing !== undefined && card.price_current !== undefined && (
                <span className="text-xs text-gray-400">
                  ${card.price_at_filing.toFixed(2)} &rarr; ${card.price_current.toFixed(2)}
                </span>
              )}
            </div>
          )}

          <span className={`px-3 py-1 rounded-full text-xs font-bold border ${dir.badge}`}>
            Insiders: {dir.label}{buyTypeLabel(card.insider_buy_type)}
          </span>
        </div>

        {/* Rally / dip context */}
        {card.price_context && (
          <p className={`mt-2 text-sm font-medium ${
            card.insider_direction === 'selling' ? 'text-amber-700' : 'text-emerald-700'
          }`}>
            {card.price_context}
          </p>
        )}

        {/* Confidence badge */}
        {conf && tier && (
          <div className={`mt-3 pt-3 border-t border-gray-100`}>
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${tier.bg} ${tier.text}`}>
                <span className={`w-2 h-2 rounded-full ${tier.dot}`}></span>
                {conf.tier} Confidence
              </span>
              <span className="text-sm text-gray-700 font-medium">{conf.win_rate}% win rate</span>
              <span className={`text-sm font-medium ${conf.avg_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {conf.avg_return >= 0 ? '+' : ''}{conf.avg_return}% avg return
              </span>
              <span className="text-xs text-gray-400">Based on {conf.sample_size} historical signals</span>
              {conf.micro_cap_warning && (
                <span className="text-xs text-amber-600 font-medium">Micro-cap adjusted</span>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-1">Pattern: {conf.pattern_label}</p>
          </div>
        )}
      </div>
    </div>
  )
}
