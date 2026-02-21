import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { alertsApi, AlertItem } from '../services/api'

const POLL_INTERVAL = 60_000 // 60 seconds

const severityColors: Record<string, string> = {
  high: 'bg-red-100 text-red-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-blue-100 text-blue-800',
}

export default function AlertBell() {
  const [unreadCount, setUnreadCount] = useState(0)
  const [recentAlerts, setRecentAlerts] = useState<AlertItem[]>([])
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Poll for unread count
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await alertsApi.getStats()
        setUnreadCount(res.data.unread)
      } catch {
        // Silently fail — bell just shows 0
      }
    }

    fetchStats()
    const interval = setInterval(fetchStats, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [])

  // Fetch recent alerts when dropdown opens
  useEffect(() => {
    if (!open) return
    const fetchRecent = async () => {
      try {
        const res = await alertsApi.getAlerts(7, undefined, false, 5)
        setRecentAlerts(res.data.alerts)
      } catch {
        // ignore
      }
    }
    fetchRecent()
  }, [open])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleDismiss = async (alertId: string) => {
    try {
      await alertsApi.acknowledge(alertId)
      setRecentAlerts((prev) => prev.filter((a) => a.id !== alertId))
      setUnreadCount((prev) => Math.max(0, prev - 1))
    } catch {
      // ignore
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 text-gray-300 hover:text-white focus:outline-none"
        aria-label="Alerts"
      >
        {/* Bell SVG */}
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>

        {/* Badge */}
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 mt-2 w-80 rounded-lg bg-white shadow-lg ring-1 ring-black ring-opacity-5 z-50">
          <div className="px-4 py-3 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-900">Alerts</span>
            {unreadCount > 0 && (
              <span className="ml-2 text-xs text-gray-500">{unreadCount} unread</span>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {recentAlerts.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-gray-500">
                No unread alerts
              </div>
            ) : (
              recentAlerts.map((alert) => (
                <div
                  key={alert.id}
                  className="px-4 py-3 border-b border-gray-50 hover:bg-gray-50"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                            severityColors[alert.severity] || severityColors.low
                          }`}
                        >
                          {alert.severity.toUpperCase()}
                        </span>
                        <span className="text-xs text-gray-400">
                          {formatRelativeTime(alert.created_at)}
                        </span>
                      </div>
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {alert.title}
                      </p>
                      <p className="text-xs text-gray-500 truncate">{alert.description}</p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDismiss(alert.id)
                      }}
                      className="flex-shrink-0 text-gray-400 hover:text-gray-600"
                      title="Dismiss"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="px-4 py-2 border-t border-gray-100">
            <Link
              to="/alerts"
              className="block text-center text-sm font-medium text-primary-600 hover:text-primary-800"
              onClick={() => setOpen(false)}
            >
              View all alerts
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60_000)

    if (diffMins < 1) return 'just now'
    if (diffMins < 60) return `${diffMins}m ago`

    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`

    const diffDays = Math.floor(diffHours / 24)
    if (diffDays < 7) return `${diffDays}d ago`

    return date.toLocaleDateString()
  } catch {
    return ''
  }
}
