import { useState } from 'react'
import { EvidenceChain as EvidenceChainType, EvidenceStep } from '../services/api'

interface EvidenceChainProps {
  chain: EvidenceChainType
  showGraphPath?: boolean
}

function EvidenceStepCard({ step, isExpanded, onToggle }: {
  step: EvidenceStep
  isExpanded: boolean
  onToggle: () => void
}) {
  const confidenceColor = step.confidence >= 0.9
    ? 'text-green-600 bg-green-100'
    : step.confidence >= 0.7
      ? 'text-yellow-600 bg-yellow-100'
      : 'text-red-600 bg-red-100'

  const claimTypeColors = {
    direct: 'bg-blue-100 text-blue-800',
    computed: 'bg-purple-100 text-purple-800',
    inferred: 'bg-orange-100 text-orange-800',
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-start justify-between text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-start space-x-3">
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary-600 text-white text-sm flex items-center justify-center font-medium">
            {step.step}
          </span>
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-900">{step.fact}</p>
            <div className="flex items-center space-x-2 mt-1">
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${claimTypeColors[step.claim_type]}`}>
                {step.claim_type}
              </span>
              {step.filing_type && (
                <span className="text-xs text-gray-500">{step.filing_type}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center space-x-2 ml-4">
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${confidenceColor}`}>
            {Math.round(step.confidence * 100)}%
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
          {step.raw_text && (
            <div className="mb-3">
              <div className="text-xs font-medium text-gray-500 mb-1">Source Text</div>
              <div className="text-sm text-gray-700 bg-white p-3 rounded border font-mono whitespace-pre-wrap max-h-32 overflow-y-auto">
                {step.raw_text}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4 text-xs">
            {step.source_section && (
              <div>
                <span className="font-medium text-gray-500">Section:</span>
                <span className="ml-1 text-gray-700">{step.source_section}</span>
              </div>
            )}
            {step.filing_accession && (
              <div>
                <span className="font-medium text-gray-500">Filing:</span>
                <span className="ml-1 text-gray-700">{step.filing_accession}</span>
              </div>
            )}
            {step.extraction_method && (
              <div>
                <span className="font-medium text-gray-500">Method:</span>
                <span className="ml-1 text-gray-700">
                  {step.extraction_method === 'rule_based' ? 'Rule-based' : 'LLM'}
                </span>
              </div>
            )}
            <div>
              <span className="font-medium text-gray-500">Hash:</span>
              <span className="ml-1 text-gray-700 font-mono">{step.raw_text_hash}</span>
            </div>
          </div>

          {step.filing_url && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <a
                href={step.filing_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center text-sm text-primary-600 hover:text-primary-800"
              >
                View Source Document
                <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function EvidenceChain({ chain, showGraphPath = true }: EvidenceChainProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set())

  const toggleStep = (step: number) => {
    const newExpanded = new Set(expandedSteps)
    if (newExpanded.has(step)) {
      newExpanded.delete(step)
    } else {
      newExpanded.add(step)
    }
    setExpandedSteps(newExpanded)
  }

  const expandAll = () => {
    setExpandedSteps(new Set(chain.evidence_steps.map(s => s.step)))
  }

  const collapseAll = () => {
    setExpandedSteps(new Set())
  }

  const confidenceColor = chain.overall_confidence >= 0.9
    ? 'text-green-600'
    : chain.overall_confidence >= 0.7
      ? 'text-yellow-600'
      : 'text-red-600'

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-gray-900">Evidence Chain</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {chain.evidence_steps.length} step{chain.evidence_steps.length !== 1 ? 's' : ''} |
              <span className={`ml-1 font-medium ${confidenceColor}`}>
                {Math.round(chain.overall_confidence * 100)}% confidence
              </span>
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={expandAll}
              className="text-xs text-primary-600 hover:text-primary-800"
            >
              Expand all
            </button>
            <span className="text-gray-300">|</span>
            <button
              onClick={collapseAll}
              className="text-xs text-primary-600 hover:text-primary-800"
            >
              Collapse all
            </button>
          </div>
        </div>
      </div>

      {/* Graph Path Visualization */}
      {showGraphPath && chain.graph_path && (
        <div className="px-4 py-2 bg-gray-50 border-b border-gray-200">
          <div className="text-xs font-medium text-gray-500 mb-1">Path</div>
          <div className="text-sm text-gray-700 font-mono overflow-x-auto whitespace-nowrap">
            {chain.graph_path.split(' | ').map((segment, i) => (
              <span key={i}>
                {i > 0 && <span className="text-gray-400 mx-2">|</span>}
                <span>{segment}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Evidence Steps */}
      <div className="p-4 space-y-3">
        {chain.evidence_steps.map((step) => (
          <EvidenceStepCard
            key={step.step}
            step={step}
            isExpanded={expandedSteps.has(step.step)}
            onToggle={() => toggleStep(step.step)}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
        Generated {chain.generated_at}
      </div>
    </div>
  )
}
