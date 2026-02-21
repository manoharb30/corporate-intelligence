import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { alertsApi, AlertItem } from '../services/api'

const severityColors: Record<string, string> = {
  high: 'bg-red-100 text-red-800 border-red-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-blue-100 text-blue-800 border-blue-200',
}

const typeLabels: Record<string, string> = {
  insider_cluster: 'Insider Cluster',
  large_purchase: 'Large Purchase',
}

export default function Alerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loading, setLoading] = useState(true)
  const [severityFilter, setSeverityFilter] = useState<string>('')
  const [showAcknowledged, setShowAcknowledged] = useState(false)

  useEffect(() => {
    const fetchAlerts = async () => {
      setLoading(true)
      try {
        const res = await alertsApi.getAlerts(
          30,
          severityFilter || undefined,
          showAcknowledged ? undefined : false,
          100,
        )
        setAlerts(res.data.alerts)
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    fetchAlerts()
  }, [severityFilter, showAcknowledged])

  const handleAcknowledge = async (alertId: string) => {
    try {
      await alertsApi.acknowledge(alertId)
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, acknowledged: true } : a)),
      )
    } catch {
      // ignore
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Alerts</h1>
        <p className="mt-1 text-sm text-gray-500">
          Real-time alerts from the Form 4 scanner — insider clusters and large purchases
        </p>
      </div>

      {/* Filters */}
      <div className="mb-4 flex items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700">Severity:</label>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="rounded-md border-gray-300 text-sm shadow-sm focus:border-primary-500 focus:ring-primary-500"
          >
            <option value="">All</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={showAcknowledged}
            onChange={(e) => setShowAcknowledged(e.target.checked)}
            className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
          />
          Show acknowledged
        </label>
      </div>

      {/* Alert list */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading alerts...</div>
      ) : alerts.length === 0 ? (
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <p className="mt-2 text-sm text-gray-500">No alerts to display</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`rounded-lg border p-4 ${
                alert.acknowledged ? 'bg-gray-50 border-gray-200 opacity-60' : 'bg-white border-gray-200 shadow-sm'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        severityColors[alert.severity] || severityColors.low
                      }`}
                    >
                      {alert.severity.toUpperCase()}
                    </span>
                    <span className="text-xs text-gray-500">
                      {typeLabels[alert.alert_type] || alert.alert_type}
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date(alert.created_at).toLocaleString()}
                    </span>
                  </div>

                  <h3 className="text-sm font-semibold text-gray-900">{alert.title}</h3>
                  <p className="mt-0.5 text-sm text-gray-600">{alert.description}</p>

                  <div className="mt-2 flex items-center gap-3">
                    <Link
                      to={`/signals?cik=${alert.company_cik}`}
                      className="text-xs font-medium text-primary-600 hover:text-primary-800"
                    >
                      View signals for {alert.company_name}
                      {alert.ticker ? ` (${alert.ticker})` : ''}
                    </Link>
                  </div>
                </div>

                {!alert.acknowledged && (
                  <button
                    onClick={() => handleAcknowledge(alert.id)}
                    className="ml-4 rounded-md bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200"
                  >
                    Dismiss
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
