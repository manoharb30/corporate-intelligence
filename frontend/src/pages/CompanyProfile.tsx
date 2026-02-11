import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { profileApi, CompanyProfile as CompanyProfileType } from '../services/api'

export default function CompanyProfile() {
  const { cik } = useParams<{ cik: string }>()
  const [profile, setProfile] = useState<CompanyProfileType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'signals' | 'people' | 'connections' | 'subsidiaries' | 'insider-trades'>('signals')

  useEffect(() => {
    if (cik) {
      loadProfile(cik)
    }
  }, [cik])

  const loadProfile = async (cik: string) => {
    setLoading(true)
    setError(null)
    try {
      const response = await profileApi.getProfile(cik)
      setProfile(response.data)
    } catch (err) {
      setError('Company not found')
      console.error('Failed to load profile:', err)
    } finally {
      setLoading(false)
    }
  }

  const getSignalTypeColor = (signalType: string) => {
    switch (signalType) {
      case 'acquisition_disposition':
      case 'control_change':
        return 'bg-red-100 text-red-800'
      case 'material_agreement':
        return 'bg-yellow-100 text-yellow-800'
      case 'executive_change':
      case 'governance_change':
        return 'bg-blue-100 text-blue-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin h-8 w-8 border-4 border-primary-500 border-t-transparent rounded-full"></div>
      </div>
    )
  }

  if (error || !profile) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">Company Not Found</h2>
        <p className="mt-2 text-gray-600">{error}</p>
        <Link to="/" className="mt-4 inline-block text-primary-600 hover:underline">
          Back to Feed
        </Link>
      </div>
    )
  }

  const { basic_info, counts, signals, connections, officers, directors, recent_subsidiaries, insider_trades, insider_trade_summary } = profile

  const getTradeColor = (code: string) => {
    switch (code) {
      case 'P':
        return 'bg-green-100 text-green-800'
      case 'S':
        return 'bg-red-100 text-red-800'
      case 'A':
        return 'bg-blue-100 text-blue-800'
      case 'M':
      case 'F':
        return 'bg-purple-100 text-purple-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div>
      {/* Back Link */}
      <Link to="/" className="inline-flex items-center text-sm text-gray-600 hover:text-primary-600 mb-4">
        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Feed
      </Link>

      {/* Company Header */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {basic_info.name}
            </h1>
            <div className="flex items-center gap-4 mt-2">
              {basic_info.ticker && (
                <span className="px-2 py-1 bg-primary-100 text-primary-800 rounded text-sm font-medium">
                  {basic_info.ticker}
                </span>
              )}
              <span className="text-sm text-gray-500">CIK: {basic_info.cik}</span>
              {basic_info.state_of_incorporation && (
                <span className="text-sm text-gray-500">
                  Incorporated in {basic_info.state_of_incorporation}
                </span>
              )}
            </div>
            {basic_info.sic_description && (
              <p className="mt-2 text-sm text-gray-600">
                {basic_info.sic_description} (SIC: {basic_info.sic})
              </p>
            )}
          </div>
          <a
            href={`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${basic_info.cik}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 text-sm"
          >
            View on SEC EDGAR
          </a>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="text-2xl font-bold text-gray-900">{counts.subsidiaries}</div>
          <div className="text-sm text-gray-600">Subsidiaries</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="text-2xl font-bold text-gray-900">{counts.officers}</div>
          <div className="text-sm text-gray-600">Officers</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="text-2xl font-bold text-gray-900">{counts.directors}</div>
          <div className="text-sm text-gray-600">Directors</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <div className="text-2xl font-bold text-gray-900">{counts.board_connections}</div>
          <div className="text-sm text-gray-600">Board Connections</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-8">
          {[
            { key: 'signals', label: 'Signal Timeline', count: signals.length },
            { key: 'people', label: 'Officers & Directors', count: officers.length + directors.length },
            { key: 'connections', label: 'Board Connections', count: connections.length },
            { key: 'subsidiaries', label: 'Subsidiaries', count: recent_subsidiaries.length },
            { key: 'insider-trades', label: 'Insider Trades', count: insider_trades?.length || 0 },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as typeof activeTab)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
              <span className="ml-2 px-2 py-0.5 bg-gray-100 rounded-full text-xs">
                {tab.count}
              </span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        {/* Signals Tab */}
        {activeTab === 'signals' && (
          <div className="divide-y divide-gray-100">
            {signals.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No signals recorded</div>
            ) : (
              signals.map((signal, idx) => (
                <div key={idx} className="p-4 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${getSignalTypeColor(signal.signal_type)}`}>
                          Item {signal.item_number}
                        </span>
                        <span className="font-medium text-gray-900">{signal.item_name}</span>
                      </div>
                      {signal.persons_mentioned.length > 0 && (
                        <div className="text-sm text-gray-600 mt-1">
                          Persons: {signal.persons_mentioned.slice(0, 3).join(', ')}
                          {signal.persons_mentioned.length > 3 && ` +${signal.persons_mentioned.length - 3} more`}
                        </div>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium text-gray-900">{signal.filing_date}</div>
                      <a
                        href={`https://www.sec.gov/Archives/edgar/data/${basic_info.cik.replace(/^0+/, '')}/${signal.accession_number.replace(/-/g, '')}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-primary-600 hover:underline"
                      >
                        View Filing
                      </a>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* People Tab */}
        {activeTab === 'people' && (
          <div className="p-6">
            <div className="grid grid-cols-2 gap-8">
              {/* Officers */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Officers</h3>
                {officers.length === 0 ? (
                  <p className="text-gray-500 text-sm">No officers recorded</p>
                ) : (
                  <ul className="space-y-3">
                    {officers.map((officer, idx) => (
                      <li key={idx} className="flex items-start">
                        <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center mr-3">
                          <span className="text-purple-600 text-sm font-medium">
                            {officer.name.charAt(0)}
                          </span>
                        </div>
                        <div>
                          <div className="font-medium text-gray-900">{officer.name}</div>
                          {officer.title && (
                            <div className="text-sm text-gray-500">{officer.title}</div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Directors */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Directors</h3>
                {directors.length === 0 ? (
                  <p className="text-gray-500 text-sm">No directors recorded</p>
                ) : (
                  <ul className="space-y-3">
                    {directors.map((director, idx) => (
                      <li key={idx} className="flex items-start">
                        <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3">
                          <span className="text-green-600 text-sm font-medium">
                            {director.name.charAt(0)}
                          </span>
                        </div>
                        <div>
                          <div className="font-medium text-gray-900">{director.name}</div>
                          {director.other_boards.length > 0 && (
                            <div className="text-sm text-gray-500">
                              Also on: {director.other_boards.slice(0, 2).join(', ')}
                              {director.other_boards.length > 2 && ` +${director.other_boards.length - 2} more`}
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Connections Tab */}
        {activeTab === 'connections' && (
          <div className="divide-y divide-gray-100">
            {connections.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No board connections found</div>
            ) : (
              connections.map((conn, idx) => (
                <div key={idx} className="p-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <Link
                        to={`/company/${conn.cik}`}
                        className="font-medium text-primary-600 hover:underline"
                      >
                        {conn.company_name}
                      </Link>
                      <div className="text-sm text-gray-600 mt-1">
                        Shared directors: {conn.shared_directors.join(', ')}
                      </div>
                    </div>
                    <div className="text-sm text-gray-500">
                      {conn.shared_directors.length} shared director{conn.shared_directors.length !== 1 ? 's' : ''}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Subsidiaries Tab */}
        {activeTab === 'subsidiaries' && (
          <div className="divide-y divide-gray-100">
            {recent_subsidiaries.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No subsidiaries recorded</div>
            ) : (
              recent_subsidiaries.map((sub, idx) => (
                <div key={idx} className="p-4 hover:bg-gray-50 flex items-center justify-between">
                  <div className="font-medium text-gray-900">{sub.name}</div>
                  {sub.jurisdiction && (
                    <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-sm">
                      {sub.jurisdiction}
                    </span>
                  )}
                </div>
              ))
            )}
            {counts.subsidiaries > recent_subsidiaries.length && (
              <div className="p-4 text-center text-sm text-gray-500">
                Showing {recent_subsidiaries.length} of {counts.subsidiaries} subsidiaries
              </div>
            )}
          </div>
        )}

        {/* Insider Trades Tab */}
        {activeTab === 'insider-trades' && (
          <div>
            {/* Summary Card */}
            {insider_trade_summary && insider_trade_summary.total > 0 && (
              <div className="p-4 border-b border-gray-100 bg-gray-50">
                <div className="flex items-center gap-4 flex-wrap">
                  <div className="text-sm">
                    <span className="font-medium text-gray-700">Unique Insiders:</span>{' '}
                    <span className="text-gray-900">{insider_trade_summary.unique_insiders}</span>
                  </div>
                  <div className="text-sm">
                    <span className="font-medium text-green-700">Buys:</span>{' '}
                    <span className="text-gray-900">{insider_trade_summary.purchases}</span>
                  </div>
                  <div className="text-sm">
                    <span className="font-medium text-red-700">Sells:</span>{' '}
                    <span className="text-gray-900">{insider_trade_summary.sales}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Transaction List */}
            <div className="divide-y divide-gray-100">
              {(!insider_trades || insider_trades.length === 0) ? (
                <div className="p-6 text-center text-gray-500">No insider trades recorded</div>
              ) : (
                insider_trades.map((trade, idx) => (
                  <div key={idx} className="p-4 hover:bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${getTradeColor(trade.transaction_code)}`}>
                            {trade.transaction_type}
                          </span>
                          <span className="font-medium text-gray-900">{trade.insider_name}</span>
                        </div>
                        {trade.insider_title && (
                          <div className="text-sm text-gray-500">{trade.insider_title}</div>
                        )}
                        <div className="text-sm text-gray-600 mt-1">
                          {trade.shares.toLocaleString()} shares of {trade.security_title}
                          {trade.price_per_share > 0 && (
                            <> @ ${trade.price_per_share.toFixed(2)}</>
                          )}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium text-gray-900">{trade.transaction_date}</div>
                        {trade.total_value > 0 && (
                          <div className={`text-sm font-medium ${trade.transaction_code === 'P' ? 'text-green-600' : trade.transaction_code === 'S' ? 'text-red-600' : 'text-gray-600'}`}>
                            ${trade.total_value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
