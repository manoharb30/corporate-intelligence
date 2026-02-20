import { useState, useRef, useEffect, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { Link } from 'react-router-dom'
import { companiesApi, graphApi, profileApi, connectionsApi, insightsApi, CompanyIntelligence, PersonSummary, ProfileSearchResult, ConnectionClaim, InsightItem } from '../services/api'

type Mode = 'entity' | 'connections' | 'interlocks'

interface ForceNode {
  id: string
  name: string
  type: string
  val: number
  color: string
  hasOtherCompanies?: boolean
}

interface ForceLink {
  source: string
  target: string
  type: string
  label?: string
}

interface ForceGraphData {
  nodes: ForceNode[]
  links: ForceLink[]
}

const NODE_COLORS: Record<string, string> = {
  Company: '#3b82f6',
  Person: '#8b5cf6',
  Jurisdiction: '#f59e0b',
  Event: '#ef4444',
  InsiderTransaction: '#10b981',
  Filing: '#6b7280',
  company: '#3b82f6',
  person: '#8b5cf6',
  subsidiary: '#f59e0b',
}

export default function NetworkPage() {
  const [mode, setMode] = useState<Mode>('entity')
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ProfileSearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [graphData, setGraphData] = useState<ForceGraphData>({ nodes: [], links: [] })
  const [selectedInfo, setSelectedInfo] = useState<string | null>(null)
  const graphRef = useRef<any>()

  // Network insights state
  const [insights, setInsights] = useState<InsightItem[]>([])

  // Connection finder state
  const [entityA, setEntityA] = useState('')
  const [entityB, setEntityB] = useState('')
  const [connectionResult, setConnectionResult] = useState<ConnectionClaim | null>(null)

  // Intelligence state
  const [selectedCompany, setSelectedCompany] = useState<CompanyIntelligence | null>(null)
  const [selectedPerson, setSelectedPerson] = useState<PersonSummary | null>(null)

  useEffect(() => {
    insightsApi.getSummary()
      .then(res => {
        const data = res.data as any
        setInsights(data.insights || data.top_insights || [])
      })
      .catch(() => {})
  }, [])

  const getInsightCategoryColor = (category: string) => {
    switch (category.toLowerCase()) {
      case 'board_interlock': return 'bg-purple-100 text-purple-800'
      case 'hub_company': return 'bg-blue-100 text-blue-800'
      case 'bridge_person': return 'bg-green-100 text-green-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const handleSearch = async () => {
    if (query.length < 2) return
    setLoading(true)
    setError(null)
    try {
      const res = await profileApi.searchCompanies(query, 10)
      setSearchResults(res.data.results)
    } catch {
      setError('Search failed')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectEntity = async (result: ProfileSearchResult) => {
    setSearchResults([])
    setQuery(result.name)
    setLoading(true)
    setError(null)

    if (mode === 'entity') {
      // Use graph API for entity graph
      try {
        const res = await graphApi.getEntityGraph(result.cik, 2, false)
        const data = res.data
        setGraphData({
          nodes: data.nodes.map(n => ({
            id: n.id,
            name: n.label || n.id,
            type: n.type,
            val: n.type === 'Company' ? 20 : 12,
            color: NODE_COLORS[n.type] || '#6b7280',
          })),
          links: data.edges.map(e => ({
            source: e.source,
            target: e.target,
            type: e.type,
          })),
        })
        setSelectedInfo(result.name)
      } catch {
        setError('Failed to load entity graph')
      }
    } else if (mode === 'interlocks') {
      // Use company intelligence for interlock view
      try {
        const searchRes = await companiesApi.search(result.name)
        const match = searchRes.data.results.find(r => r.in_graph && r.company_id)
        if (match && match.company_id) {
          const intRes = await companiesApi.getIntelligence(match.company_id)
          setSelectedCompany(intRes.data)
          buildIntelligenceGraph(intRes.data)
          setSelectedInfo(intRes.data.company_name)
        } else {
          setError('Company not in database')
        }
      } catch {
        setError('Failed to load intelligence')
      }
    }
    setLoading(false)
  }

  const buildIntelligenceGraph = (company: CompanyIntelligence) => {
    const nodes: ForceNode[] = []
    const links: ForceLink[] = []

    nodes.push({ id: company.company_id, name: company.company_name, type: 'company', val: 30, color: '#3b82f6' })

    company.officers.forEach(p => {
      nodes.push({
        id: p.id, name: p.name, type: 'person',
        val: p.other_companies_count > 0 ? 15 : 10,
        color: p.other_companies_count > 0 ? '#ef4444' : '#8b5cf6',
        hasOtherCompanies: p.other_companies_count > 0,
      })
      links.push({ source: p.id, target: company.company_id, type: 'OFFICER_OF', label: p.title || 'Officer' })
    })

    const officerIds = new Set(company.officers.map(o => o.id))
    company.directors.forEach(p => {
      if (!officerIds.has(p.id)) {
        nodes.push({
          id: p.id, name: p.name, type: 'person',
          val: p.other_companies_count > 0 ? 15 : 10,
          color: p.other_companies_count > 0 ? '#ef4444' : '#10b981',
          hasOtherCompanies: p.other_companies_count > 0,
        })
      }
      links.push({ source: p.id, target: company.company_id, type: 'DIRECTOR_OF', label: 'Director' })
    })

    company.subsidiaries.forEach(s => {
      nodes.push({ id: s.id, name: s.name, type: 'subsidiary', val: 12, color: '#f59e0b' })
      links.push({ source: company.company_id, target: s.id, type: 'OWNS', label: 'Owns' })
    })

    setGraphData({ nodes, links })
  }

  const handleFindConnection = async () => {
    if (!entityA || !entityB) return
    setLoading(true)
    setError(null)
    setConnectionResult(null)
    try {
      const res = await connectionsApi.findConnection(entityA, entityB, 4, true)
      setConnectionResult(res.data)
      setSelectedInfo(`${res.data.entity_a_name} → ${res.data.entity_b_name}`)
    } catch (err: any) {
      if (err?.response?.status === 404) {
        setError('No connection found between these entities')
      } else {
        setError('Connection search failed')
      }
    } finally {
      setLoading(false)
    }
  }

  const nodeCanvasObject = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.name || ''
    const fontSize = 12 / globalScale
    ctx.font = `${fontSize}px Sans-Serif`
    const size = (node.val || 10) / 2

    ctx.beginPath()
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI)
    ctx.fillStyle = node.color || '#6b7280'
    ctx.fill()

    if (node.hasOtherCompanies) {
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 2 / globalScale
      ctx.stroke()
    }

    ctx.textAlign = 'center'
    ctx.fillStyle = '#ffffff'
    const truncated = label.length > 15 ? label.substring(0, 12) + '...' : label
    ctx.fillText(truncated, node.x, node.y + size + fontSize)
  }, [])

  useEffect(() => {
    if (graphRef.current && graphData.nodes.length > 0) {
      setTimeout(() => graphRef.current?.zoomToFit(400, 50), 500)
    }
  }, [graphData])

  const modeTabs: { key: Mode; label: string }[] = [
    { key: 'entity', label: 'Entity Graph' },
    { key: 'connections', label: 'Connection Finder' },
    { key: 'interlocks', label: 'Board Interlocks' },
  ]

  return (
    <div className="flex h-[calc(100vh-6rem)]">
      {/* Left Sidebar */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col shrink-0">
        <div className="p-4 border-b border-gray-200">
          <h1 className="text-lg font-bold text-gray-900 mb-3">Network</h1>

          {/* Mode tabs */}
          <div className="flex gap-1 mb-3">
            {modeTabs.map(tab => (
              <button
                key={tab.key}
                onClick={() => { setMode(tab.key); setGraphData({ nodes: [], links: [] }); setError(null); setSelectedInfo(null); setSelectedCompany(null); setConnectionResult(null) }}
                className={`px-2.5 py-1.5 rounded text-xs font-medium transition-colors flex-1 ${
                  mode === tab.key ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Search (entity/interlocks mode) */}
          {mode !== 'connections' && (
            <div className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="Search company..."
                className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
              <button
                onClick={handleSearch}
                disabled={loading || query.length < 2}
                className="px-3 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-400 text-sm"
              >
                Go
              </button>
            </div>
          )}

          {/* Connection finder inputs */}
          {mode === 'connections' && (
            <div className="space-y-2">
              <input
                type="text"
                value={entityA}
                onChange={e => setEntityA(e.target.value)}
                placeholder="Entity A (name)"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
              <input
                type="text"
                value={entityB}
                onChange={e => setEntityB(e.target.value)}
                placeholder="Entity B (name)"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
              />
              <button
                onClick={handleFindConnection}
                disabled={loading || !entityA || !entityB}
                className="w-full px-3 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-gray-400 text-sm"
              >
                {loading ? 'Searching...' : 'Find Connection'}
              </button>
            </div>
          )}
        </div>

        {/* Search results dropdown */}
        {searchResults.length > 0 && (
          <div className="border-b border-gray-200 max-h-48 overflow-y-auto">
            {searchResults.map((r, idx) => (
              <button
                key={idx}
                onClick={() => handleSelectEntity(r)}
                className="w-full text-left px-4 py-2.5 hover:bg-gray-50 text-sm border-b border-gray-100 last:border-0"
              >
                <span className="font-medium text-gray-900">{r.name}</span>
                {r.ticker && <span className="text-gray-500 ml-1">({r.ticker})</span>}
              </button>
            ))}
          </div>
        )}

        {/* Error */}
        {error && <div className="px-4 py-2 text-sm text-red-600 bg-red-50">{error}</div>}

        {/* Info panel */}
        <div className="flex-1 overflow-y-auto p-4">
          {selectedInfo && (
            <div className="mb-3">
              <h3 className="font-semibold text-gray-900 text-sm">{selectedInfo}</h3>
              <p className="text-xs text-gray-500 mt-0.5">{graphData.nodes.length} nodes, {graphData.links.length} edges</p>
            </div>
          )}

          {/* Connection result */}
          {connectionResult && (
            <div className="space-y-2">
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-sm font-medium text-green-800">{connectionResult.claim}</p>
                <p className="text-xs text-green-600 mt-1">
                  {connectionResult.path_length} hops | {connectionResult.claim_type}
                </p>
              </div>
              {connectionResult.evidence_chain.evidence_steps.map((step, idx) => (
                <div key={idx} className="p-2 bg-gray-50 rounded text-xs">
                  <span className="font-medium text-gray-700">Step {step.step}:</span>{' '}
                  <span className="text-gray-600">{step.fact}</span>
                </div>
              ))}
            </div>
          )}

          {/* Intelligence sidebar */}
          {selectedCompany && (
            <div className="space-y-3">
              {selectedCompany.red_flags.length > 0 && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <h4 className="text-xs font-semibold text-red-800 mb-1">Red Flags ({selectedCompany.red_flags.length})</h4>
                  {selectedCompany.red_flags.map((f, i) => (
                    <p key={i} className="text-xs text-red-700">{f.description}</p>
                  ))}
                </div>
              )}

              {selectedPerson && (
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="flex justify-between items-start">
                    <h4 className="text-sm font-bold text-blue-900">{selectedPerson.name}</h4>
                    <button onClick={() => setSelectedPerson(null)} className="text-blue-700 font-bold">x</button>
                  </div>
                  <p className="text-xs text-blue-700 mt-1">Connected to {selectedPerson.other_companies_count} other companies</p>
                </div>
              )}

              <div>
                <h4 className="text-xs font-semibold text-gray-600 uppercase mb-1">Officers ({selectedCompany.officers.length})</h4>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {selectedCompany.officers.slice(0, 10).map(p => (
                    <div key={p.id} className="text-xs">
                      <span className={p.other_companies_count > 0 ? 'text-red-600 font-medium' : 'text-gray-700'}>
                        {p.name}
                      </span>
                      {p.other_companies_count > 0 && <span className="text-xs text-red-500 ml-1">+{p.other_companies_count}</span>}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold text-gray-600 uppercase mb-1">Directors ({selectedCompany.directors.length})</h4>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {selectedCompany.directors.slice(0, 10).map(p => (
                    <div key={p.id} className="text-xs">
                      <span className={p.other_companies_count > 0 ? 'text-red-600 font-medium' : 'text-gray-700'}>
                        {p.name}
                      </span>
                      {p.other_companies_count > 0 && <span className="text-xs text-red-500 ml-1">+{p.other_companies_count}</span>}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Network Alerts */}
          {insights.length > 0 && !selectedCompany && !connectionResult && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Network Alerts</h4>
              <div className="space-y-2">
                {insights.slice(0, 6).map((insight, idx) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-gray-50">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${getInsightCategoryColor(insight.category)}`}>
                        {insight.category.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-gray-900">{insight.headline}</p>
                    <p className="text-xs text-gray-600 mt-0.5">{insight.description}</p>
                    {insight.entities?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {insight.entities.slice(0, 3).map((entity, eidx) =>
                          entity.cik ? (
                            <Link key={eidx} to={`/signals?cik=${entity.cik}`} className="text-xs text-primary-600 hover:underline">
                              {entity.name}
                            </Link>
                          ) : (
                            <span key={eidx} className="text-xs text-gray-500">{entity.name}</span>
                          )
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Legend */}
          {graphData.nodes.length > 0 && (
            <div className="mt-4 pt-3 border-t border-gray-200">
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Legend</h4>
              <div className="space-y-1">
                {Object.entries(NODE_COLORS).filter(([k]) => k.charAt(0) === k.charAt(0).toUpperCase()).map(([type, color]) => (
                  <div key={type} className="flex items-center gap-2 text-xs text-gray-600">
                    <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: color }}></span>
                    {type}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main graph area */}
      <div className="flex-1 bg-gray-900 relative">
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            nodeLabel={(node: any) => node.name}
            nodeRelSize={6}
            linkColor={() => '#4b5563'}
            linkWidth={1.5}
            nodeCanvasObject={nodeCanvasObject}
            nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
              const size = (node.val || 10) / 2
              ctx.beginPath()
              ctx.arc(node.x, node.y, size + 5, 0, 2 * Math.PI)
              ctx.fillStyle = color
              ctx.fill()
            }}
            onNodeClick={(node: any) => {
              if (node.hasOtherCompanies && selectedCompany) {
                const person = [...(selectedCompany.officers || []), ...(selectedCompany.directors || [])]
                  .find(p => p.id === node.id)
                if (person) setSelectedPerson(person)
              }
            }}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <p className="text-xl mb-2">Search for a company to explore its network</p>
              <p className="text-sm text-gray-600">
                {mode === 'entity' && 'Visualize corporate entity relationships'}
                {mode === 'connections' && 'Find hidden paths between two entities'}
                {mode === 'interlocks' && 'Discover board-level connections'}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
