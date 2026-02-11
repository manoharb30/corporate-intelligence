import { useState } from 'react'
import { RiskAssessment as RiskAssessmentType, RiskFactor } from '../services/api'
import RiskBadge from './RiskBadge'
import EvidenceChain from './EvidenceChain'

interface RiskAssessmentProps {
  assessment: RiskAssessmentType
  showEvidenceChain?: boolean
}

function RiskFactorCard({ factor, isExpanded, onToggle }: {
  factor: RiskFactor
  isExpanded: boolean
  onToggle: () => void
}) {
  const confidenceColor = factor.confidence >= 0.9
    ? 'bg-green-100 text-green-800'
    : factor.confidence >= 0.7
      ? 'bg-yellow-100 text-yellow-800'
      : 'bg-red-100 text-red-800'

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center space-x-3">
          <span className="flex-shrink-0 w-8 h-8 rounded-full bg-red-100 text-red-700 text-sm flex items-center justify-center font-bold">
            +{factor.weight}
          </span>
          <div>
            <p className="text-sm font-medium text-gray-900">{factor.factor_name}</p>
            <p className="text-xs text-gray-500">{factor.source_type}</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${confidenceColor}`}>
            {Math.round(factor.confidence * 100)}%
          </span>
          <svg
            className={`w-5 h-5 text-gray-400 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
          <p className="text-sm text-gray-700 mb-3">{factor.factor_description}</p>

          {factor.raw_text && (
            <div className="mb-3">
              <div className="text-xs font-medium text-gray-500 mb-1">Evidence</div>
              <div className="text-sm text-gray-700 bg-white p-2 rounded border font-mono whitespace-pre-wrap">
                {factor.raw_text}
              </div>
            </div>
          )}

          {factor.filing_url && (
            <a
              href={factor.filing_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center text-sm text-primary-600 hover:text-primary-800"
            >
              View Source ({factor.filing_type})
              <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          )}
        </div>
      )}
    </div>
  )
}

export default function RiskAssessment({ assessment, showEvidenceChain = false }: RiskAssessmentProps) {
  const [expandedFactors, setExpandedFactors] = useState<Set<number>>(new Set())
  const [showFullEvidence, setShowFullEvidence] = useState(false)

  const toggleFactor = (index: number) => {
    const newExpanded = new Set(expandedFactors)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedFactors(newExpanded)
  }

  // Risk score gauge
  const scorePercentage = Math.min(assessment.risk_score, 100)
  const gaugeColor = assessment.risk_level === 'CRITICAL' ? '#dc2626'
    : assessment.risk_level === 'HIGH' ? '#ea580c'
    : assessment.risk_level === 'MEDIUM' ? '#ca8a04'
    : '#16a34a'

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Header with Score */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Risk Assessment</h2>
            {assessment.entity_name && (
              <p className="text-sm text-gray-500">{assessment.entity_name}</p>
            )}
          </div>
          <RiskBadge level={assessment.risk_level} score={assessment.risk_score} size="lg" />
        </div>

        {/* Score Gauge */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
            <span>0</span>
            <span>Risk Score</span>
            <span>100+</span>
          </div>
          <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${scorePercentage}%`,
                backgroundColor: gaugeColor,
              }}
            />
          </div>
        </div>

        {/* Summary Stats */}
        <div className="mt-4 grid grid-cols-3 gap-4 text-center">
          <div className="p-2 bg-gray-50 rounded">
            <div className="text-2xl font-bold text-gray-900">{assessment.risk_score}</div>
            <div className="text-xs text-gray-500">Total Score</div>
          </div>
          <div className="p-2 bg-gray-50 rounded">
            <div className="text-2xl font-bold text-gray-900">{assessment.factor_count}</div>
            <div className="text-xs text-gray-500">Risk Factors</div>
          </div>
          <div className="p-2 bg-gray-50 rounded">
            <div className="text-2xl font-bold text-gray-900">
              {Math.round(assessment.evidence_chain.overall_confidence * 100)}%
            </div>
            <div className="text-xs text-gray-500">Confidence</div>
          </div>
        </div>
      </div>

      {/* Risk Factors */}
      {assessment.risk_factors.length > 0 ? (
        <div className="p-6">
          <h3 className="text-sm font-medium text-gray-900 mb-3">
            Contributing Factors ({assessment.risk_factors.length})
          </h3>
          <div className="space-y-3">
            {assessment.risk_factors.map((factor, index) => (
              <RiskFactorCard
                key={index}
                factor={factor}
                isExpanded={expandedFactors.has(index)}
                onToggle={() => toggleFactor(index)}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="p-6 text-center text-gray-500">
          <svg className="w-12 h-12 mx-auto text-green-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="font-medium">No risk factors detected</p>
          <p className="text-sm">This entity has a clean risk profile based on available data.</p>
        </div>
      )}

      {/* Evidence Chain (Optional) */}
      {showEvidenceChain && assessment.evidence_chain.evidence_steps.length > 0 && (
        <div className="border-t border-gray-200">
          <button
            onClick={() => setShowFullEvidence(!showFullEvidence)}
            className="w-full px-6 py-3 flex items-center justify-between text-left hover:bg-gray-50"
          >
            <span className="text-sm font-medium text-gray-700">
              Full Evidence Chain ({assessment.evidence_chain.evidence_steps.length} steps)
            </span>
            <svg
              className={`w-5 h-5 text-gray-400 transform transition-transform ${showFullEvidence ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {showFullEvidence && (
            <div className="p-6 pt-0">
              <EvidenceChain chain={assessment.evidence_chain} showGraphPath={false} />
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="px-6 py-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
        Assessed on {assessment.assessed_at}
      </div>
    </div>
  )
}
