import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  companiesApi,
  citationsApi,
  connectionsApi,
  Company,
  Citation,
  CitationSummary,
  RiskAssessment as RiskAssessmentType,
} from '../services/api'
import RiskAssessment from '../components/RiskAssessment'
import RiskBadge from '../components/RiskBadge'

export default function CompanyDetail() {
  const { id } = useParams<{ id: string }>()
  const [company, setCompany] = useState<Company | null>(null)
  const [subsidiaries, setSubsidiaries] = useState<Company[]>([])
  const [riskAssessment, setRiskAssessment] = useState<RiskAssessmentType | null>(null)
  const [citations, setCitations] = useState<Citation[]>([])
  const [citationSummary, setCitationSummary] = useState<CitationSummary | null>(null)
  const [showCitations, setShowCitations] = useState(false)
  const [expandedCitation, setExpandedCitation] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (id) {
      loadCompanyData()
    }
  }, [id])

  const loadCompanyData = async () => {
    if (!id) return
    setLoading(true)
    try {
      const [companyRes, subsidRes, riskRes, citationSumRes] = await Promise.all([
        companiesApi.get(id),
        companiesApi.getSubsidiaries(id, 3),
        connectionsApi.getRiskAssessment(id).catch(() => ({ data: null })),
        citationsApi.getSummary(id).catch(() => ({ data: null })),
      ])
      setCompany(companyRes.data)
      setSubsidiaries(subsidRes.data)
      setRiskAssessment(riskRes.data)
      setCitationSummary(citationSumRes.data)
    } catch (error) {
      console.error('Failed to load company:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadCitations = async () => {
    if (!id) return
    try {
      const res = await citationsApi.getEntityCitations(id, 20)
      setCitations(res.data)
      setShowCitations(true)
    } catch (error) {
      console.error('Failed to load citations:', error)
    }
  }

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!company) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Company not found</p>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <Link to="/companies" className="text-primary-600 hover:text-primary-800 text-sm">
          &larr; Back to Companies
        </Link>
      </div>

      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{company.name}</h1>
            <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
              {company.cik && (
                <div>
                  <span className="text-gray-500">CIK:</span> {company.cik}
                </div>
              )}
              {company.lei && (
                <div>
                  <span className="text-gray-500">LEI:</span> {company.lei}
                </div>
              )}
              {company.jurisdiction && (
                <div>
                  <span className="text-gray-500">Jurisdiction:</span> {company.jurisdiction}
                </div>
              )}
              {company.status && (
                <div>
                  <span className="text-gray-500">Status:</span> {company.status}
                </div>
              )}
            </div>
          </div>
          {riskAssessment && (
            <RiskBadge
              level={riskAssessment.risk_level}
              score={riskAssessment.risk_score}
              size="lg"
            />
          )}
        </div>

        <div className="mt-4 flex items-center space-x-3">
          <Link
            to={`/graph?entity=${id}`}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700"
          >
            View in Graph
          </Link>
          <Link
            to={`/connections?from=${id}&fromName=${encodeURIComponent(company.name)}`}
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50"
          >
            Find Connections
          </Link>
        </div>
      </div>

      {/* Risk Assessment */}
      {riskAssessment && (
        <div className="mb-6">
          <RiskAssessment assessment={riskAssessment} showEvidenceChain={true} />
        </div>
      )}

      {/* Subsidiaries */}
      {subsidiaries.length > 0 && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Subsidiaries</h2>
          <ul className="divide-y divide-gray-200">
            {subsidiaries.map((sub) => (
              <li key={sub.id} className="py-3">
                <Link
                  to={`/companies/${sub.id}`}
                  className="text-primary-600 hover:text-primary-800"
                >
                  {sub.name}
                </Link>
                {sub.jurisdiction && (
                  <span className="ml-2 text-sm text-gray-500">({sub.jurisdiction})</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Data Provenance / Citations */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">Data Provenance</h2>
          {citationSummary && citationSummary.total_citations > 0 && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              {Math.round(citationSummary.avg_confidence * 100)}% avg confidence
            </span>
          )}
        </div>

        {citationSummary && citationSummary.total_citations > 0 ? (
          <>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="p-3 bg-gray-50 rounded text-center">
                <div className="text-2xl font-bold text-gray-900">{citationSummary.total_citations}</div>
                <div className="text-xs text-gray-500">Total Citations</div>
              </div>
              <div className="p-3 bg-gray-50 rounded text-center">
                <div className="text-lg font-semibold text-gray-900">
                  {citationSummary.filing_types.join(', ') || 'N/A'}
                </div>
                <div className="text-xs text-gray-500">Filing Types</div>
              </div>
              <div className="p-3 bg-gray-50 rounded text-center">
                <div className="text-lg font-semibold text-gray-900">
                  {citationSummary.extraction_methods.map(m => m === 'rule_based' ? 'Rule-based' : 'LLM').join(', ')}
                </div>
                <div className="text-xs text-gray-500">Extraction Methods</div>
              </div>
            </div>

            {!showCitations ? (
              <button
                onClick={loadCitations}
                className="w-full py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                View Citation Details
              </button>
            ) : (
              <div className="space-y-3">
                <div className="text-sm font-medium text-gray-700 mb-2">Source Citations</div>
                {citations.map((citation, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-md">
                    <button
                      onClick={() => setExpandedCitation(expandedCitation === idx ? null : idx)}
                      className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50"
                    >
                      <div className="flex-1">
                        <div className="flex items-center space-x-2">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                            {citation.fact_type.replace('_', ' ')}
                          </span>
                          <span className="text-sm text-gray-900">{citation.related_entity}</span>
                          {citation.fact_value && (
                            <span className="text-sm text-gray-500">- {citation.fact_value}</span>
                          )}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {citation.filing_type} ({citation.filing_accession})
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          citation.confidence >= 0.9 ? 'bg-green-100 text-green-800' :
                          citation.confidence >= 0.7 ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {Math.round(citation.confidence * 100)}%
                        </span>
                        <svg
                          className={`w-5 h-5 text-gray-400 transform transition-transform ${expandedCitation === idx ? 'rotate-180' : ''}`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </button>

                    {expandedCitation === idx && (
                      <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
                        {citation.raw_text && (
                          <div className="mb-3">
                            <div className="text-xs font-medium text-gray-500 mb-1">Source Text</div>
                            <div className="text-sm text-gray-700 bg-white p-2 rounded border font-mono whitespace-pre-wrap">
                              {citation.raw_text}
                            </div>
                          </div>
                        )}
                        {citation.section_name && (
                          <div className="mb-3">
                            <div className="text-xs font-medium text-gray-500 mb-1">Section</div>
                            <div className="text-sm text-gray-700">{citation.section_name}</div>
                          </div>
                        )}
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-gray-500">
                            Extraction: {citation.extraction_method === 'rule_based' ? 'Rule-based' : 'LLM'}
                          </span>
                          {citation.filing_url && (
                            <a
                              href={citation.filing_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary-600 hover:text-primary-800 flex items-center"
                            >
                              View on SEC EDGAR
                              <svg className="w-4 h-4 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                              </svg>
                            </a>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-gray-500">No citation data available for this entity.</p>
        )}
      </div>
    </div>
  )
}
