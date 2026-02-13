import { InsiderContextData } from '../services/api'

interface VerdictCardProps {
  signalLevel: string
  combinedSignalLevel?: string
  signalSummary: string
  insiderContext?: InsiderContextData | null
  itemNumbers: string[]
  companyName: string
}

const accentColors: Record<string, string> = {
  critical: 'border-purple-500 bg-purple-50',
  high_bearish: 'border-red-700 bg-red-50',
  high: 'border-red-500 bg-red-50',
  medium: 'border-yellow-500 bg-yellow-50',
  low: 'border-blue-500 bg-blue-50',
}

const accentText: Record<string, string> = {
  critical: 'text-purple-800',
  high_bearish: 'text-red-800',
  high: 'text-red-700',
  medium: 'text-yellow-800',
  low: 'text-blue-700',
}

const levelLabel: Record<string, string> = {
  critical: 'CRITICAL',
  high_bearish: 'HIGH BEARISH',
  high: 'HIGH',
  medium: 'MEDIUM',
  low: 'LOW',
}

function formatValue(val: number): string {
  if (val >= 1e6) return `$${(val / 1e6).toFixed(1)}M`
  if (val >= 1e3) return `$${Math.round(val / 1e3)}K`
  return ''
}

function generateVerdict(props: VerdictCardProps): string {
  const { combinedSignalLevel, signalSummary, insiderContext, itemNumbers } = props
  const level = combinedSignalLevel || props.signalLevel
  const parts: string[] = []

  // Signal basis
  if (itemNumbers.includes('1.01')) {
    parts.push('Material Agreement filed')
    if (itemNumbers.includes('5.02') || itemNumbers.includes('5.03')) {
      parts.push('with leadership/governance changes')
    }
  } else {
    parts.push(signalSummary)
  }

  // Insider activity
  if (insiderContext && insiderContext.trade_count > 0) {
    const dir = insiderContext.net_direction
    const buyVal = insiderContext.total_buy_value
    const sellVal = insiderContext.total_sell_value
    const count = insiderContext.trade_count

    if (dir === 'buying') {
      const valStr = formatValue(buyVal)
      parts.push(`+ ${count} insider trade${count !== 1 ? 's' : ''} net BUYING${valStr ? ` (${valStr})` : ''}`)
    } else if (dir === 'selling') {
      const valStr = formatValue(sellVal)
      parts.push(`+ ${count} insider trade${count !== 1 ? 's' : ''} net SELLING${valStr ? ` (${valStr})` : ''}`)
    } else if (dir === 'mixed') {
      parts.push(`+ ${count} insider trade${count !== 1 ? 's' : ''} (mixed)`)
    }

    if (insiderContext.cluster_activity) {
      parts.push('+ cluster activity detected')
    }

    if (insiderContext.person_matches.length > 0) {
      parts.push(`+ ${insiderContext.person_matches.length} filing-insider overlap${insiderContext.person_matches.length > 1 ? 's' : ''}`)
    }
  }

  return `${levelLabel[level] || level}: ${parts.join(' ')}`
}

export default function VerdictCard(props: VerdictCardProps) {
  const level = props.combinedSignalLevel || props.signalLevel
  const verdict = generateVerdict(props)

  return (
    <div className={`rounded-lg border-l-4 p-5 ${accentColors[level] || accentColors.low}`}>
      <h3 className={`text-lg font-bold mb-2 ${accentText[level] || accentText.low}`}>
        The Verdict
      </h3>
      <p className={`font-medium ${accentText[level] || accentText.low}`}>{verdict}</p>

      {props.insiderContext?.person_matches && props.insiderContext.person_matches.length > 0 && (
        <div className="mt-3 space-y-1">
          {props.insiderContext.person_matches.map((match, idx) => (
            <p key={idx} className="text-sm text-gray-700 bg-white/60 rounded px-2 py-1">
              {match}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
