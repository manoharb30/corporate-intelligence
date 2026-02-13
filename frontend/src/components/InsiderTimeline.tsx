import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { EventTimelineEntry } from '../services/api'

interface InsiderTimelineProps {
  entries: EventTimelineEntry[]
  maxItems?: number
  highlightDate?: string | null  // date to scroll to and highlight
}

export default function InsiderTimeline({ entries, maxItems = 30, highlightDate }: InsiderTimelineProps) {
  const [showAll, setShowAll] = useState(false)
  const visible = showAll ? entries : entries.slice(0, maxItems)

  const getTradeColor = (tradeType?: string) => {
    switch (tradeType) {
      case 'buy': return 'text-green-700 bg-green-50 border-green-200'
      case 'sell': return 'text-red-700 bg-red-50 border-red-200'
      default: return 'text-gray-700 bg-gray-50 border-gray-200'
    }
  }

  const getDotClass = (entry: EventTimelineEntry) => {
    if (entry.is_current) return 'bg-primary-500 border-primary-500 w-4 h-4 ring-2 ring-primary-200'
    if (entry.notable) return 'bg-amber-500 border-amber-500 w-4 h-4 ring-2 ring-amber-200'
    if (entry.type === 'trade') {
      if (entry.trade_type === 'buy') return 'bg-green-400 border-green-400 w-3 h-3'
      if (entry.trade_type === 'sell') return 'bg-red-400 border-red-400 w-3 h-3'
      return 'bg-gray-300 border-gray-300 w-3 h-3'
    }
    if (entry.signal_level === 'high') return 'bg-red-500 border-red-500 w-3 h-3'
    if (entry.signal_level === 'medium') return 'bg-yellow-500 border-yellow-500 w-3 h-3'
    return 'bg-gray-300 border-gray-300 w-3 h-3'
  }

  // Auto-expand if highlighted entry is beyond visible range
  useEffect(() => {
    if (highlightDate && !showAll) {
      const idx = entries.findIndex(e => e.date === highlightDate)
      if (idx >= maxItems) {
        setShowAll(true)
      }
    }
  }, [highlightDate, entries, maxItems, showAll])

  // Callback ref to scroll to the first highlighted element
  const scrollRef = useCallback((node: HTMLDivElement | null) => {
    if (node && highlightDate) {
      setTimeout(() => {
        node.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }, 100)
    }
  }, [highlightDate])

  if (visible.length === 0) {
    return <p className="text-gray-500 text-sm">No timeline data available.</p>
  }

  // Find the first matching index so we only attach scrollRef once
  const firstHighlightIdx = highlightDate ? visible.findIndex(e => e.date === highlightDate) : -1

  return (
    <div className="relative">
      <div className="absolute left-[7px] top-0 bottom-0 w-0.5 bg-gray-200"></div>
      <div className="space-y-3">
        {visible.map((entry, idx) => {
          const isHighlighted = highlightDate === entry.date
          const isFirstHighlight = idx === firstHighlightIdx
          return (
          <div
            key={idx}
            ref={isFirstHighlight ? scrollRef : undefined}
            className={`relative pl-8 py-1.5 transition-all duration-500 ${
              isHighlighted ? 'bg-indigo-50 rounded-lg border border-indigo-300 px-3 ml-6 ring-2 ring-indigo-200' :
              entry.is_current ? 'bg-primary-50 rounded-lg border border-primary-200 px-3 ml-6' :
              entry.notable ? 'bg-amber-50 rounded-lg border border-amber-200 px-3 ml-6' : ''
            }`}
          >
            <div className={`absolute left-0 top-2.5 rounded-full border-2 ${getDotClass(entry)}`}
              style={entry.is_current || entry.notable || isHighlighted ? { left: '-1.5rem' } : {}}
            />

            <div className="flex items-center gap-2 flex-wrap text-xs mb-0.5">
              <span className="font-mono text-gray-500">{entry.date}</span>
              {entry.type === 'event' && entry.signal_level && (
                <span className={`px-1.5 py-0.5 rounded font-semibold uppercase text-white ${
                  entry.signal_level === 'high' ? 'bg-red-500' :
                  entry.signal_level === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                }`}>
                  {entry.signal_level}
                </span>
              )}
              {entry.type === 'trade' && (
                <span className={`px-1.5 py-0.5 rounded font-medium border ${getTradeColor(entry.trade_type)}`}>
                  {entry.trade_type === 'buy' ? '\u2191 Buy' : entry.trade_type === 'sell' ? '\u2193 Sell' : 'Trade'}
                </span>
              )}
              {entry.is_current && (
                <span className="px-1.5 py-0.5 bg-primary-100 text-primary-700 rounded font-medium">Current</span>
              )}
              {entry.notable && entry.notable_reasons?.map((reason, i) => (
                <span key={i} className="px-1.5 py-0.5 bg-amber-100 text-amber-800 border border-amber-300 rounded font-semibold">
                  {reason}
                </span>
              ))}
            </div>
            <p className="text-sm font-medium text-gray-900">
              {entry.type === 'event' && entry.accession_number && !entry.is_current ? (
                <Link to={`/signal/${encodeURIComponent(entry.accession_number)}`} className="hover:text-primary-600">
                  {entry.description}
                </Link>
              ) : (
                entry.description
              )}
            </p>
            <p className="text-xs text-gray-500 truncate">{entry.detail}</p>
          </div>
          )
        })}
      </div>
      {entries.length > maxItems && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="text-xs text-primary-600 hover:text-primary-800 font-medium mt-3 pl-8"
        >
          {showAll ? `Show less (${maxItems})` : `Show all ${entries.length} entries`}
        </button>
      )}
    </div>
  )
}
