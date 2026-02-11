import { useState, useCallback, useRef, useEffect } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { companiesApi, CompanySearchResult, CompanyIntelligence, PersonSummary } from '../services/api'

interface GraphNode {
  id: string
  name: string
  type: 'company' | 'person' | 'subsidiary'
  val: number
  color: string
  hasOtherCompanies?: boolean
}

interface GraphLink {
  source: string
  target: string
  type: string
  label: string
}

interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
}

export default function Intelligence() {
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<CompanySearchResult[]>([])
  const [selectedCompany, setSelectedCompany] = useState<CompanyIntelligence | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] })
  const [selectedPerson, setSelectedPerson] = useState<PersonSummary | null>(null)
  const graphRef = useRef<any>()

  const handleSearch = async () => {
    if (query.length < 2) return
    setLoading(true)
    setError(null)
    setSelectedCompany(null)
    setGraphData({ nodes: [], links: [] })
    try {
      const response = await companiesApi.search(query)
      setSearchResults(response.data.results)
    } catch (err) {
      setError('Search failed')
    } finally {
      setLoading(false)
    }
  }

  const buildGraphData = (company: CompanyIntelligence): GraphData => {
    const nodes: GraphNode[] = []
    const links: GraphLink[] = []

    // Center company node
    nodes.push({
      id: company.company_id,
      name: company.company_name,
      type: 'company',
      val: 30,
      color: '#3b82f6'
    })

    // Officers
    company.officers.forEach(person => {
      nodes.push({
        id: person.id,
        name: person.name,
        type: 'person',
        val: person.other_companies_count > 0 ? 15 : 10,
        color: person.other_companies_count > 0 ? '#ef4444' : '#8b5cf6',
        hasOtherCompanies: person.other_companies_count > 0
      })
      links.push({
        source: person.id,
        target: company.company_id,
        type: 'OFFICER_OF',
        label: person.title || 'Officer'
      })
    })

    // Directors (avoid duplicates)
    const officerIds = new Set(company.officers.map(o => o.id))
    company.directors.forEach(person => {
      if (!officerIds.has(person.id)) {
        nodes.push({
          id: person.id,
          name: person.name,
          type: 'person',
          val: person.other_companies_count > 0 ? 15 : 10,
          color: person.other_companies_count > 0 ? '#ef4444' : '#10b981',
          hasOtherCompanies: person.other_companies_count > 0
        })
      }
      links.push({
        source: person.id,
        target: company.company_id,
        type: 'DIRECTOR_OF',
        label: 'Director'
      })
    })

    // Subsidiaries
    company.subsidiaries.forEach(sub => {
      nodes.push({
        id: sub.id,
        name: sub.name,
        type: 'subsidiary',
        val: 12,
        color: '#f59e0b'
      })
      links.push({
        source: company.company_id,
        target: sub.id,
        type: 'OWNS',
        label: 'Owns'
      })
    })

    return { nodes, links }
  }

  const handleSelectCompany = async (result: CompanySearchResult) => {
    if (!result.in_graph || !result.company_id) {
      setError(`${result.name} is not in our database yet. CIK: ${result.cik}`)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await companiesApi.getIntelligence(result.company_id)
      setSelectedCompany(response.data)
      setSearchResults([])
      setGraphData(buildGraphData(response.data))
    } catch (err) {
      setError('Failed to load company intelligence')
    } finally {
      setLoading(false)
    }
  }

  const handleNodeClick = useCallback((node: any) => {
    console.log('Node clicked:', node)
    if (node.hasOtherCompanies) {
      const person = [...(selectedCompany?.officers || []), ...(selectedCompany?.directors || [])]
        .find(p => p.id === node.id)
      if (person) {
        setSelectedPerson(person)
        // Also fetch their other companies
        alert(`${person.name} is connected to ${person.other_companies_count} other company(ies). Click to see details in the sidebar.`)
      }
    } else if (node.type === 'subsidiary') {
      alert(`Subsidiary: ${node.name}\nClick to explore this company's network.`)
    }
  }, [selectedCompany])

  // Center graph on load
  useEffect(() => {
    if (graphRef.current && graphData.nodes.length > 0) {
      setTimeout(() => {
        graphRef.current.zoomToFit(400, 50)
      }, 500)
    }
  }, [graphData])

  return (
    <div className="h-screen flex flex-col">
      {/* Search Header */}
      <div className="p-4 bg-white border-b">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Company Intelligence</h1>
        <div className="flex gap-2 max-w-2xl">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search company name or ticker..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSearch}
            disabled={loading || query.length < 2}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
          >
            {loading ? '...' : 'Search'}
          </button>
        </div>

        {error && <div className="mt-2 text-red-600 text-sm">{error}</div>}

        {/* Search Results Dropdown */}
        {searchResults.length > 0 && (
          <div className="absolute z-10 mt-1 w-full max-w-2xl bg-white border rounded-lg shadow-lg">
            {searchResults.map((result, idx) => (
              <div
                key={idx}
                onClick={() => handleSelectCompany(result)}
                className="p-3 hover:bg-gray-50 cursor-pointer flex justify-between items-center border-b last:border-b-0"
              >
                <div>
                  <p className="font-medium">{result.name}</p>
                  <p className="text-sm text-gray-500">CIK: {result.cik || 'N/A'}</p>
                </div>
                <span className={`px-2 py-1 rounded text-xs ${
                  result.in_graph ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                }`}>
                  {result.in_graph ? 'In DB' : 'SEC'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Main Content */}
      {selectedCompany && (
        <div className="flex-1 flex">
          {/* Graph View */}
          <div className="flex-1 bg-gray-900 relative">
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              nodeLabel={(node: any) => `${node.name}${node.hasOtherCompanies ? ' (CLICK TO EXPLORE)' : ''}`}
              nodeRelSize={6}
              linkColor={() => '#4b5563'}
              linkWidth={2}
              nodeCanvasObject={(node: any, ctx, globalScale) => {
                const label = node.name
                const fontSize = 12 / globalScale
                ctx.font = `${fontSize}px Sans-Serif`

                // Draw node circle
                const size = node.val || 10
                ctx.beginPath()
                ctx.arc(node.x, node.y, size / 2, 0, 2 * Math.PI)
                ctx.fillStyle = node.color
                ctx.fill()

                // Add border for clickable nodes
                if (node.hasOtherCompanies) {
                  ctx.strokeStyle = '#ffffff'
                  ctx.lineWidth = 2 / globalScale
                  ctx.stroke()
                }

                // Draw label
                ctx.textAlign = 'center'
                ctx.textBaseline = 'middle'
                ctx.fillStyle = '#ffffff'
                const maxWidth = 80 / globalScale
                const truncatedLabel = label.length > 15 ? label.substring(0, 12) + '...' : label
                ctx.fillText(truncatedLabel, node.x, node.y + size / 2 + fontSize)
              }}
              nodePointerAreaPaint={(node: any, color, ctx) => {
                const size = node.val || 10
                ctx.beginPath()
                ctx.arc(node.x, node.y, size / 2 + 5, 0, 2 * Math.PI)
                ctx.fillStyle = color
                ctx.fill()
              }}
              onNodeClick={(node: any) => {
                console.log('NODE CLICKED:', node)
                if (node.type === 'company') {
                  // Main company node - do nothing for now
                  return
                }
                if (node.hasOtherCompanies) {
                  const person = [...(selectedCompany?.officers || []), ...(selectedCompany?.directors || [])]
                    .find(p => p.id === node.id)
                  if (person) {
                    setSelectedPerson(person)
                  }
                } else if (node.type === 'subsidiary') {
                  // Could navigate to subsidiary in the future
                  console.log('Subsidiary clicked:', node.name)
                }
              }}
            />

            {/* Legend */}
            <div className="absolute top-4 left-4 bg-white/90 p-3 rounded-lg text-sm">
              <div className="font-semibold mb-2">Legend</div>
              <div className="flex items-center gap-2 mb-1">
                <span className="w-3 h-3 rounded-full bg-blue-500"></span>
                <span>Company</span>
              </div>
              <div className="flex items-center gap-2 mb-1">
                <span className="w-3 h-3 rounded-full bg-purple-500"></span>
                <span>Officer</span>
              </div>
              <div className="flex items-center gap-2 mb-1">
                <span className="w-3 h-3 rounded-full bg-green-500"></span>
                <span>Director</span>
              </div>
              <div className="flex items-center gap-2 mb-1">
                <span className="w-3 h-3 rounded-full bg-red-500"></span>
                <span>Connected to other companies (click!)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-amber-500"></span>
                <span>Subsidiary</span>
              </div>
            </div>

            {/* Company Info Overlay */}
            <div className="absolute top-4 right-4 bg-white/90 p-4 rounded-lg max-w-xs">
              <h2 className="font-bold text-lg">{selectedCompany.company_name}</h2>
              <p className="text-sm text-gray-600 mb-2">CIK: {selectedCompany.cik || 'N/A'}</p>
              <div className="text-sm space-y-1">
                <div>Officers: {selectedCompany.officers.length}</div>
                <div>Directors: {selectedCompany.directors.length}</div>
                <div>Subsidiaries: {selectedCompany.subsidiaries.length}</div>
              </div>
              <button
                onClick={() => { setSelectedCompany(null); setGraphData({ nodes: [], links: [] }); setQuery(''); }}
                className="mt-3 text-sm text-blue-600 hover:underline"
              >
                ← New Search
              </button>
            </div>
          </div>

          {/* Side Panel - Red Flags & Details */}
          <div className="w-80 bg-white border-l overflow-y-auto">
            {/* Red Flags */}
            {selectedCompany.red_flags.length > 0 && (
              <div className="p-4 bg-red-50 border-b border-red-200">
                <h3 className="font-semibold text-red-800 mb-2">
                  ⚠️ Red Flags ({selectedCompany.red_flags.length})
                </h3>
                {selectedCompany.red_flags.map((flag, idx) => (
                  <div key={idx} className="text-sm text-red-700 mb-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs mr-2 ${
                      flag.severity === 'high' ? 'bg-red-200' :
                      flag.severity === 'medium' ? 'bg-orange-200' : 'bg-yellow-200'
                    }`}>
                      {flag.severity.toUpperCase()}
                    </span>
                    {flag.description}
                  </div>
                ))}
              </div>
            )}

            {/* Person Details Panel */}
            {selectedPerson && (
              <div className="p-4 bg-blue-100 border-b-4 border-blue-500">
                <div className="flex justify-between items-start">
                  <h3 className="font-bold text-blue-900 text-lg">{selectedPerson.name}</h3>
                  <button onClick={() => setSelectedPerson(null)} className="text-blue-700 text-xl font-bold hover:text-blue-900">×</button>
                </div>
                <p className="text-blue-800 mt-2 font-medium">
                  🔗 Connected to {selectedPerson.other_companies_count} other {selectedPerson.other_companies_count === 1 ? 'company' : 'companies'}
                </p>
                {selectedPerson.title && (
                  <p className="text-blue-700 text-sm mt-1">Title: {selectedPerson.title}</p>
                )}
                <button className="mt-3 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm w-full">
                  Expand Network (Coming Soon)
                </button>
              </div>
            )}

            {/* Officers List */}
            <div className="p-4 border-b">
              <h3 className="font-semibold mb-2">Officers ({selectedCompany.officers.length})</h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {selectedCompany.officers.slice(0, 10).map(p => (
                  <div key={p.id} className="text-sm">
                    <span className={p.other_companies_count > 0 ? 'text-red-600 font-medium' : ''}>
                      {p.name}
                    </span>
                    {p.other_companies_count > 0 && (
                      <span className="text-xs text-red-500 ml-1">+{p.other_companies_count}</span>
                    )}
                    {p.title && <span className="text-gray-500 text-xs block">{p.title}</span>}
                  </div>
                ))}
              </div>
            </div>

            {/* Directors List */}
            <div className="p-4 border-b">
              <h3 className="font-semibold mb-2">Directors ({selectedCompany.directors.length})</h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {selectedCompany.directors.slice(0, 10).map(p => (
                  <div key={p.id} className="text-sm">
                    <span className={p.other_companies_count > 0 ? 'text-red-600 font-medium' : ''}>
                      {p.name}
                    </span>
                    {p.other_companies_count > 0 && (
                      <span className="text-xs text-red-500 ml-1">+{p.other_companies_count}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Subsidiaries */}
            <div className="p-4">
              <h3 className="font-semibold mb-2">Subsidiaries ({selectedCompany.subsidiaries.length})</h3>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {selectedCompany.subsidiaries.slice(0, 10).map(s => (
                  <div key={s.id} className="text-sm text-gray-700">{s.name}</div>
                ))}
                {selectedCompany.subsidiaries.length > 10 && (
                  <div className="text-xs text-gray-500">+{selectedCompany.subsidiaries.length - 10} more</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!selectedCompany && !loading && searchResults.length === 0 && (
        <div className="flex-1 flex items-center justify-center text-gray-500">
          <div className="text-center">
            <div className="text-6xl mb-4">🔍</div>
            <p className="text-xl">Search for a company to explore its network</p>
            <p className="text-sm mt-2">Try: Nikola, Apple, Tesla</p>
          </div>
        </div>
      )}
    </div>
  )
}
