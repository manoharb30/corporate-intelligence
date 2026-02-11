import { ConnectionClaim } from '../services/api'
import EvidenceChain from './EvidenceChain'

interface ConnectionResultProps {
  connection: ConnectionClaim
}

const connectionTypeLabels: Record<string, { label: string; color: string }> = {
  ownership: { label: 'Ownership', color: 'bg-blue-100 text-blue-800' },
  directorship: { label: 'Directorship', color: 'bg-purple-100 text-purple-800' },
  executive: { label: 'Executive', color: 'bg-indigo-100 text-indigo-800' },
  address: { label: 'Shared Address', color: 'bg-yellow-100 text-yellow-800' },
  jurisdiction: { label: 'Jurisdiction', color: 'bg-green-100 text-green-800' },
  indirect: { label: 'Indirect', color: 'bg-gray-100 text-gray-800' },
}

export default function ConnectionResult({ connection }: ConnectionResultProps) {
  const typeConfig = connectionTypeLabels[connection.connection_type] || connectionTypeLabels.indirect

  const confidenceColor = connection.evidence_chain.overall_confidence >= 0.9
    ? 'text-green-600'
    : connection.evidence_chain.overall_confidence >= 0.7
      ? 'text-yellow-600'
      : 'text-red-600'

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 bg-gradient-to-r from-primary-50 to-white border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center space-x-2 mb-1">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${typeConfig.color}`}>
                {typeConfig.label}
              </span>
              <span className="text-sm text-gray-500">
                {connection.path_length} hop{connection.path_length !== 1 ? 's' : ''}
              </span>
            </div>
            <h3 className="text-lg font-semibold text-gray-900">
              Connection Found
            </h3>
          </div>
          <div className="text-right">
            <div className={`text-2xl font-bold ${confidenceColor}`}>
              {Math.round(connection.evidence_chain.overall_confidence * 100)}%
            </div>
            <div className="text-xs text-gray-500">confidence</div>
          </div>
        </div>
      </div>

      {/* Visual Path */}
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center justify-center space-x-4">
          {/* Entity A */}
          <div className="flex-shrink-0 text-center">
            <div className="w-16 h-16 rounded-full bg-primary-100 flex items-center justify-center mx-auto mb-2">
              <svg className="w-8 h-8 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <div className="text-sm font-medium text-gray-900 max-w-24 truncate" title={connection.entity_a_name}>
              {connection.entity_a_name}
            </div>
          </div>

          {/* Path Arrow */}
          <div className="flex-1 flex items-center">
            <div className="flex-1 h-0.5 bg-gray-300"></div>
            <div className="mx-2 px-3 py-1 bg-white border border-gray-300 rounded-full text-xs text-gray-600">
              {connection.path_length} step{connection.path_length !== 1 ? 's' : ''}
            </div>
            <div className="flex-1 h-0.5 bg-gray-300"></div>
            <svg className="w-4 h-4 text-gray-400 -ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>

          {/* Entity B */}
          <div className="flex-shrink-0 text-center">
            <div className="w-16 h-16 rounded-full bg-primary-100 flex items-center justify-center mx-auto mb-2">
              <svg className="w-8 h-8 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div className="text-sm font-medium text-gray-900 max-w-24 truncate" title={connection.entity_b_name}>
              {connection.entity_b_name}
            </div>
          </div>
        </div>
      </div>

      {/* Claim */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="text-sm text-gray-500 mb-1">Claim</div>
        <p className="text-gray-900 font-medium">{connection.claim}</p>
      </div>

      {/* Evidence Chain */}
      <div className="p-6">
        <EvidenceChain chain={connection.evidence_chain} showGraphPath={true} />
      </div>
    </div>
  )
}
