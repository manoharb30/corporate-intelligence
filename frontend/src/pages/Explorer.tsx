import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import CytoscapeComponent from 'react-cytoscapejs'
import type cytoscape from 'cytoscape'
import { explorerApi, ExplorerGraphData, ExplorerSearchResult } from '../services/api'

type Mode = 'company' | 'person'

function formatValue(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`
  return `$${v.toLocaleString()}`
}

// Convert our graph data to Cytoscape elements
function toCytoscapeElements(data: ExplorerGraphData): cytoscape.ElementDefinition[] {
  const elements: cytoscape.ElementDefinition[] = []

  for (const node of data.nodes) {
    elements.push({
      data: {
        id: node.id,
        label: node.label,
        type: node.type,
        name: node.name,
        ...node.metadata,
      },
    })
  }

  for (const edge of data.edges) {
    elements.push({
      data: {
        id: `${edge.source}-${edge.type}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        type: edge.type,
        ...edge.metadata,
      },
    })
  }

  return elements
}

// Cytoscape stylesheet
const cytoscapeStylesheet: cytoscape.Stylesheet[] = [
  // Company nodes — large blue
  {
    selector: 'node[type="company"]',
    style: {
      'background-color': '#3B82F6',
      'label': 'data(label)',
      'color': '#ffffff',
      'text-outline-color': '#1e3a5f',
      'text-outline-width': 2,
      'font-size': '14px',
      'font-weight': 'bold' as const,
      'width': 60,
      'height': 60,
      'text-valign': 'center' as const,
      'text-halign': 'center' as const,
    },
  },
  // Person nodes — medium gray
  {
    selector: 'node[type="person"]',
    style: {
      'background-color': '#64748B',
      'label': 'data(label)',
      'color': '#e2e8f0',
      'text-outline-color': '#1e293b',
      'text-outline-width': 1,
      'font-size': '10px',
      'width': 35,
      'height': 35,
      'text-valign': 'bottom' as const,
      'text-halign': 'center' as const,
      'text-margin-y': 8,
    },
  },
  // Person with cross-company activity — highlighted
  {
    selector: 'node[type="person"][cross_company_count > 0]',
    style: {
      'background-color': '#8B5CF6',
      'border-color': '#a78bfa',
      'border-width': 3,
    },
  },
  // Event nodes — small orange
  {
    selector: 'node[type="event"]',
    style: {
      'background-color': '#F59E0B',
      'label': 'data(label)',
      'color': '#fef3c7',
      'text-outline-color': '#78350f',
      'text-outline-width': 1,
      'font-size': '8px',
      'width': 25,
      'height': 25,
      'shape': 'diamond' as const,
      'text-valign': 'bottom' as const,
      'text-halign': 'center' as const,
      'text-margin-y': 6,
    },
  },
  // Activist nodes — small purple
  {
    selector: 'node[type="activist"]',
    style: {
      'background-color': '#8B5CF6',
      'label': 'data(label)',
      'color': '#ede9fe',
      'text-outline-color': '#4c1d95',
      'text-outline-width': 1,
      'font-size': '8px',
      'width': 25,
      'height': 25,
      'shape': 'triangle' as const,
      'text-valign': 'bottom' as const,
      'text-halign': 'center' as const,
      'text-margin-y': 6,
    },
  },
  // Buy edges — green
  {
    selector: 'edge[type="buy"]',
    style: {
      'line-color': '#22C55E',
      'target-arrow-color': '#22C55E',
      'target-arrow-shape': 'triangle' as const,
      'width': 2,
      'curve-style': 'bezier' as const,
      'opacity': 0.8,
    },
  },
  // Sell edges — red
  {
    selector: 'edge[type="sell"]',
    style: {
      'line-color': '#EF4444',
      'target-arrow-color': '#EF4444',
      'target-arrow-shape': 'triangle' as const,
      'width': 2,
      'curve-style': 'bezier' as const,
      'opacity': 0.8,
    },
  },
  // Event edges — orange dashed
  {
    selector: 'edge[type="event"]',
    style: {
      'line-color': '#F59E0B',
      'line-style': 'dashed' as const,
      'width': 1,
      'curve-style': 'bezier' as const,
      'opacity': 0.5,
    },
  },
  // Activist edges — purple dashed
  {
    selector: 'edge[type="activist"]',
    style: {
      'line-color': '#8B5CF6',
      'line-style': 'dashed' as const,
      'width': 1,
      'curve-style': 'bezier' as const,
      'opacity': 0.5,
    },
  },
  // Officer edges — blue dashed
  {
    selector: 'edge[type="officer"]',
    style: {
      'line-color': '#60A5FA',
      'line-style': 'dashed' as const,
      'width': 1,
      'curve-style': 'bezier' as const,
      'opacity': 0.4,
    },
  },
  // Director edges — slate dashed
  {
    selector: 'edge[type="director"]',
    style: {
      'line-color': '#94A3B8',
      'line-style': 'dashed' as const,
      'width': 1,
      'curve-style': 'bezier' as const,
      'opacity': 0.4,
    },
  },
  // Expandable indicator — cross-company companies
  {
    selector: 'node[type="company"][?is_cross_company]',
    style: {
      'border-color': '#a78bfa',
      'border-width': 3,
      'border-style': 'dashed' as const,
    },
  },
  // Hover state
  {
    selector: 'node:active',
    style: {
      'overlay-color': '#ffffff',
      'overlay-opacity': 0.2,
    },
  },
  // Grabbed/selected state
  {
    selector: 'node:selected',
    style: {
      'border-color': '#ffffff',
      'border-width': 3,
    },
  },
]

export default function Explorer() {
  const [mode, setMode] = useState<Mode>('company')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<ExplorerSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [graphData, setGraphData] = useState<ExplorerGraphData | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedLabel, setSelectedLabel] = useState('')
  const [selectedNode, setSelectedNode] = useState<Record<string, unknown> | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  // Memoize elements — only recalculate when graphData changes, not on every render
  const cyElements = useMemo(() => {
    if (!graphData) return []
    return toCytoscapeElements(graphData)
  }, [graphData])

  const [expanding, setExpanding] = useState(false)
  const expandedNodes = useRef<Set<string>>(new Set())

  // Expand a node — fetch its connections and merge into graph
  const expandNode = useCallback(async (nodeData: Record<string, unknown>) => {
    const cy = cyRef.current
    if (!cy || expanding) return

    const nodeType = nodeData.type as string
    const nodeId = nodeData.id as string

    // Already expanded?
    if (expandedNodes.current.has(nodeId)) return

    let newData: ExplorerGraphData | null = null
    setExpanding(true)

    try {
      if (nodeType === 'person') {
        const res = await explorerApi.expandPerson(nodeData.label as string || nodeData.name as string)
        newData = res.data
      } else if (nodeType === 'company') {
        const res = await explorerApi.expandCompany(nodeData.ticker as string || nodeData.label as string)
        newData = res.data
      }
    } catch {
      // ignore
    } finally {
      setExpanding(false)
    }

    if (!newData || !cy) return

    expandedNodes.current.add(nodeId)

    // Get existing node IDs
    const existingIds = new Set(cy.nodes().map(n => n.id()))
    const existingEdgeIds = new Set(cy.edges().map(e => e.id()))

    // Add only new nodes and edges
    const newElements = toCytoscapeElements(newData)
    const toAdd: cytoscape.ElementDefinition[] = []

    for (const el of newElements) {
      if (el.data.source) {
        // Edge
        const edgeId = el.data.id as string
        if (!existingEdgeIds.has(edgeId)) {
          // Only add if both source and target exist (or will exist)
          const srcExists = existingIds.has(el.data.source as string) || newElements.some(n => !n.data.source && n.data.id === el.data.source)
          const tgtExists = existingIds.has(el.data.target as string) || newElements.some(n => !n.data.source && n.data.id === el.data.target)
          if (srcExists && tgtExists) {
            toAdd.push(el)
          }
        }
      } else {
        // Node
        if (!existingIds.has(el.data.id as string)) {
          toAdd.push(el)
        }
      }
    }

    if (toAdd.length === 0) return

    // Position new nodes near the clicked node
    const clickedNode = cy.getElementById(nodeId)
    const clickedPos = clickedNode.position()

    // Add elements
    const added = cy.add(toAdd)

    // Position new nodes in a circle around clicked node
    const newNodes = added.nodes()
    const count = newNodes.length
    if (count > 0 && clickedPos) {
      newNodes.forEach((node, i) => {
        const angle = (2 * Math.PI * i) / count
        const radius = 150
        node.position({
          x: clickedPos.x + radius * Math.cos(angle),
          y: clickedPos.y + radius * Math.sin(angle),
        })
      })

      // Run layout only on new nodes, keeping existing ones locked
      cy.nodes().not(newNodes).lock()
      cy.layout({
        name: 'cose',
        animate: true,
        animationDuration: 600,
        fit: false,
        nodeRepulsion: () => 6000,
        idealEdgeLength: () => 100,
        gravity: 0.2,
        numIter: 100,
        padding: 30,
      } as cytoscape.LayoutOptions).run()

      // Unlock after animation
      setTimeout(() => {
        cy.nodes().unlock()
      }, 700)
    }
  }, [expanding])

  // Handle Cytoscape instance
  const handleCy = useCallback((cy: cytoscape.Core) => {
    cyRef.current = cy
    // Node click handler
    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      const data = node.data()
      setSelectedNode(data)
      expandNode(data)
    })
    // Background click — deselect
    cy.on('tap', (evt) => {
      if (evt.target === cy) setSelectedNode(null)
    })
  }, [expandNode])

  // Autocomplete search
  useEffect(() => {
    if (query.length < 2) {
      setResults([])
      return
    }
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await explorerApi.search(query, mode)
        setResults(res.data)
      } catch {
        setResults([])
      } finally {
        setSearching(false)
      }
    }, 250)
    return () => clearTimeout(timer)
  }, [query, mode])

  // Select a result
  const handleSelect = async (result: ExplorerSearchResult) => {
    setQuery('')
    setResults([])
    setSelectedLabel(result.label)
    setSelectedNode(null)
    expandedNodes.current = new Set()
    setLoading(true)
    try {
      const q = mode === 'company' ? (result.ticker || result.id) : result.name
      const res = await explorerApi.graph(q, mode)
      setGraphData(res.data)
    } catch {
      setGraphData(null)
    } finally {
      setLoading(false)
    }
  }

  // Switch mode
  const handleModeChange = (newMode: Mode) => {
    setMode(newMode)
    setQuery('')
    setResults([])
    setGraphData(null)
    setSelectedLabel('')
    inputRef.current?.focus()
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="py-6 mb-4">
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">Graph Explorer</h1>
        <p className="text-sm text-gray-500 mt-1">
          Explore insider trading connections across companies and people.
        </p>
      </div>

      {/* Mode toggle + Search */}
      <div className="mb-6">
        {/* Mode buttons */}
        <div className="flex gap-2 mb-3">
          <button
            onClick={() => handleModeChange('company')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === 'company'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Explore by Company
          </button>
          <button
            onClick={() => handleModeChange('person')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === 'person'
                ? 'bg-gray-900 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Explore by Person
          </button>
        </div>

        {/* Search input */}
        <div className="relative">
          <div className="relative">
            <svg className="absolute left-3 top-3 w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={mode === 'company' ? 'Type a ticker or company name...' : 'Type an insider name...'}
              className="w-full pl-10 pr-4 py-3 bg-white border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm"
              autoFocus
            />
            {searching && (
              <div className="absolute right-3 top-3">
                <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full"></div>
              </div>
            )}
          </div>

          {/* Autocomplete dropdown */}
          {results.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-xl shadow-xl border border-gray-200 z-50 max-h-64 overflow-y-auto">
              {results.map((r) => (
                <button
                  key={r.id}
                  onClick={() => handleSelect(r)}
                  className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-center justify-between border-b border-gray-100 last:border-0 transition-colors"
                >
                  <div>
                    <span className="text-sm font-medium text-gray-900">{r.label}</span>
                  </div>
                  {r.ticker && (
                    <span className="text-xs text-gray-400 font-mono">{r.ticker}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-24">
          <div className="animate-spin h-10 w-10 border-4 border-blue-500 border-t-transparent rounded-full"></div>
        </div>
      )}

      {/* Graph + Side Panel */}
      {!loading && graphData && (
        <div className="flex gap-4" style={{ height: 'calc(100vh - 280px)' }}>
          {/* Graph canvas */}
          <div className="flex-1 bg-gray-900 rounded-2xl overflow-hidden relative">
            <CytoscapeComponent
              elements={cyElements}
              stylesheet={cytoscapeStylesheet}
              layout={{
                name: 'cose',
                animate: true,
                animationDuration: 800,
                nodeRepulsion: () => 8000,
                idealEdgeLength: () => 120,
                gravity: 0.3,
                numIter: 200,
                padding: 40,
              } as cytoscape.LayoutOptions}
              style={{ width: '100%', height: '100%' }}
              cy={handleCy}
              minZoom={0.3}
              maxZoom={3}
            />
            {/* Legend */}
            <div className="absolute bottom-4 left-4 flex gap-3 bg-gray-800/80 rounded-lg px-3 py-2">
              <span className="flex items-center gap-1 text-[10px] text-gray-300">
                <span className="w-2 h-2 rounded-full bg-green-500"></span> Buy
              </span>
              <span className="flex items-center gap-1 text-[10px] text-gray-300">
                <span className="w-2 h-2 rounded-full bg-red-500"></span> Sell
              </span>
              <span className="flex items-center gap-1 text-[10px] text-gray-300">
                <span className="w-2 h-2 rounded-full bg-amber-500"></span> 8-K Event
              </span>
              <span className="flex items-center gap-1 text-[10px] text-gray-300">
                <span className="w-2 h-2 rounded-full bg-purple-500"></span> 13D Filing
              </span>
              <span className="flex items-center gap-1 text-[10px] text-gray-300">
                <span className="w-2 h-2 rounded-full bg-blue-400"></span> Officer/Director
              </span>
            </div>
            {/* Top bar — node count + reset */}
            <div className="absolute top-4 right-4 flex items-center gap-2">
              {expanding && (
                <div className="bg-gray-800/80 rounded-lg px-3 py-1.5 flex items-center gap-2">
                  <div className="animate-spin h-3 w-3 border-2 border-blue-400 border-t-transparent rounded-full"></div>
                  <span className="text-xs text-blue-300">Expanding...</span>
                </div>
              )}
              <div className="bg-gray-800/80 rounded-lg px-3 py-1.5 text-xs text-gray-400">
                {cyRef.current ? cyRef.current.nodes().length : graphData.nodes.length} nodes · {cyRef.current ? cyRef.current.edges().length : graphData.edges.length} edges
              </div>
              {expandedNodes.current.size > 0 && (
                <button
                  onClick={() => {
                    expandedNodes.current = new Set()
                    setSelectedNode(null)
                    // Re-render with original data
                    const original = graphData
                    setGraphData(null)
                    setTimeout(() => setGraphData(original), 50)
                  }}
                  className="bg-gray-800/80 hover:bg-gray-700/80 rounded-lg px-3 py-1.5 text-xs text-gray-300 transition-colors"
                >
                  Reset
                </button>
              )}
            </div>
          </div>

          {/* Side panel */}
          <div className="w-80 bg-white rounded-2xl border border-gray-200 shadow-sm overflow-y-auto p-5">
            {/* Summary header */}
            <div className="mb-4">
              <h2 className="text-lg font-bold text-gray-900">
                {graphData.summary.company || graphData.summary.person || selectedLabel}
              </h2>
              {graphData.summary.ticker && (
                <span className="text-sm text-gray-400">{graphData.summary.ticker}</span>
              )}
              <div className="flex gap-3 mt-3">
                {graphData.summary.total_buy_value > 0 && (
                  <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-1.5 text-center flex-1">
                    <div className="text-sm font-bold text-green-700">{formatValue(graphData.summary.total_buy_value)}</div>
                    <div className="text-[10px] text-green-600">Buying</div>
                  </div>
                )}
                {graphData.summary.total_sell_value > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-1.5 text-center flex-1">
                    <div className="text-sm font-bold text-red-700">{formatValue(graphData.summary.total_sell_value)}</div>
                    <div className="text-[10px] text-red-600">Selling</div>
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-2 mt-3 text-xs text-gray-500">
                {(graphData.summary.total_insiders ?? 0) > 0 && <span>{graphData.summary.total_insiders} insiders</span>}
                {(graphData.summary.event_count ?? 0) > 0 && <span>· {graphData.summary.event_count} events</span>}
                {(graphData.summary.activist_count ?? 0) > 0 && <span>· {graphData.summary.activist_count} activist filings</span>}
                {(graphData.summary.officer_count ?? 0) > 0 && <span>· {graphData.summary.officer_count} officers</span>}
                {(graphData.summary.director_count ?? 0) > 0 && <span>· {graphData.summary.director_count} directors</span>}
              </div>
            </div>

            {/* Selected node detail */}
            {selectedNode && (
              <div className="mb-4 border border-gray-200 rounded-xl overflow-hidden">
                {/* Header with type badge */}
                <div className={`px-4 py-2.5 flex items-center gap-2 ${
                  selectedNode.type === 'company' ? 'bg-blue-50 border-b border-blue-100' :
                  selectedNode.type === 'person' ? 'bg-gray-50 border-b border-gray-100' :
                  selectedNode.type === 'event' ? 'bg-amber-50 border-b border-amber-100' :
                  'bg-purple-50 border-b border-purple-100'
                }`}>
                  <span className={`w-2.5 h-2.5 rounded-full ${
                    selectedNode.type === 'company' ? 'bg-blue-500' :
                    selectedNode.type === 'person' ? 'bg-gray-500' :
                    selectedNode.type === 'event' ? 'bg-amber-500' :
                    'bg-purple-500'
                  }`}></span>
                  <span className="text-xs font-semibold text-gray-500 uppercase">{selectedNode.type as string}</span>
                </div>

                <div className="p-4 space-y-3">
                  {/* Name */}
                  <p className="text-sm font-bold text-gray-900">{selectedNode.name as string || selectedNode.label as string}</p>

                  {/* Company detail */}
                  {selectedNode.type === 'company' && (
                    <>
                      {selectedNode.ticker && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">Ticker:</span>
                          <span className="text-xs font-mono font-bold text-gray-700">{selectedNode.ticker as string}</span>
                        </div>
                      )}
                      {selectedNode.sic && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">Industry:</span>
                          <span className="text-xs text-gray-700">{selectedNode.sic as string}</span>
                        </div>
                      )}
                      {selectedNode.is_cross_company && (
                        <div className="bg-purple-50 border border-purple-200 rounded px-2 py-1">
                          <span className="text-[10px] text-purple-700">Connected via cross-company insider</span>
                        </div>
                      )}
                    </>
                  )}

                  {/* Person detail */}
                  {selectedNode.type === 'person' && (
                    <>
                      {selectedNode.title && (
                        <p className="text-xs text-gray-500">{selectedNode.title as string}</p>
                      )}
                      {selectedNode.role && (
                        <span className="inline-block px-2 py-0.5 bg-blue-50 border border-blue-200 rounded text-[10px] text-blue-700">
                          {selectedNode.role as string}
                        </span>
                      )}
                      {/* Buy/Sell breakdown */}
                      {((selectedNode.buy_value as number) > 0 || (selectedNode.sell_value as number) > 0) && (
                        <div className="space-y-1.5">
                          {(selectedNode.buy_value as number) > 0 && (
                            <div className="flex items-center justify-between bg-green-50 rounded px-2.5 py-1.5">
                              <span className="text-xs text-green-700">Open Market Buying</span>
                              <div className="text-right">
                                <span className="text-xs font-bold text-green-700">{formatValue(selectedNode.buy_value as number)}</span>
                                {(selectedNode.buy_count as number) > 0 && (
                                  <span className="text-[10px] text-green-600 ml-1">({selectedNode.buy_count as number} trades)</span>
                                )}
                              </div>
                            </div>
                          )}
                          {(selectedNode.sell_value as number) > 0 && (
                            <div className="flex items-center justify-between bg-red-50 rounded px-2.5 py-1.5">
                              <span className="text-xs text-red-700">Open Market Selling</span>
                              <div className="text-right">
                                <span className="text-xs font-bold text-red-700">{formatValue(selectedNode.sell_value as number)}</span>
                                {(selectedNode.sell_count as number) > 0 && (
                                  <span className="text-[10px] text-red-600 ml-1">({selectedNode.sell_count as number} trades)</span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                      {selectedNode.latest_date && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">Latest trade:</span>
                          <span className="text-xs font-mono text-gray-600">{selectedNode.latest_date as string}</span>
                        </div>
                      )}
                      {/* Cross-company callout */}
                      {(selectedNode.cross_company_count as number) > 0 && (
                        <div className="bg-purple-50 border border-purple-200 rounded-lg p-2.5">
                          <div className="flex items-center gap-1.5 mb-1">
                            <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                            <span className="text-[10px] font-bold text-purple-800 uppercase">Cross-Company Activity</span>
                          </div>
                          <p className="text-xs text-purple-700">
                            This insider also trades at {selectedNode.cross_company_count as number} other {(selectedNode.cross_company_count as number) === 1 ? 'company' : 'companies'}.
                          </p>
                        </div>
                      )}
                    </>
                  )}

                  {/* Event detail */}
                  {selectedNode.type === 'event' && (
                    <>
                      {selectedNode.date && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">Filed:</span>
                          <span className="text-xs font-mono text-gray-600">{selectedNode.date as string}</span>
                        </div>
                      )}
                      {selectedNode.item && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">Item:</span>
                          <span className="text-xs font-mono text-gray-700">{selectedNode.item as string}</span>
                        </div>
                      )}
                      {selectedNode.is_ma && (
                        <span className="inline-block px-2 py-0.5 bg-amber-100 border border-amber-200 rounded text-[10px] text-amber-800 font-medium">
                          Material Signal
                        </span>
                      )}
                    </>
                  )}

                  {/* Activist detail */}
                  {selectedNode.type === 'activist' && (
                    <>
                      {selectedNode.filer && (
                        <p className="text-xs text-gray-700">{selectedNode.filer as string}</p>
                      )}
                      {selectedNode.percentage && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">Stake:</span>
                          <span className="text-sm font-bold text-purple-700">{selectedNode.percentage as number}%</span>
                        </div>
                      )}
                      {selectedNode.date && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-400">Filed:</span>
                          <span className="text-xs font-mono text-gray-600">{selectedNode.date as string}</span>
                        </div>
                      )}
                      {selectedNode.form_type && (
                        <span className="inline-block px-2 py-0.5 bg-purple-100 border border-purple-200 rounded text-[10px] text-purple-800 font-medium">
                          {selectedNode.form_type as string}
                        </span>
                      )}
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Node list */}
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">Nodes</h3>
              <div className="space-y-1">
                {graphData.nodes
                  .filter(n => n.type === 'person')
                  .sort((a, b) => {
                    const aVal = ((a.metadata.buy_value as number) || 0) + ((a.metadata.sell_value as number) || 0)
                    const bVal = ((b.metadata.buy_value as number) || 0) + ((b.metadata.sell_value as number) || 0)
                    return bVal - aVal
                  })
                  .map(n => {
                    const buyVal = (n.metadata.buy_value as number) || 0
                    const sellVal = (n.metadata.sell_value as number) || 0
                    const role = n.metadata.role as string
                    return (
                      <button
                        key={n.id}
                        onClick={() => {
                          setSelectedNode(n.metadata)
                          // Highlight in graph
                          if (cyRef.current) {
                            cyRef.current.elements().removeClass('highlighted')
                            cyRef.current.getElementById(n.id).addClass('highlighted')
                          }
                        }}
                        className="w-full text-left px-2 py-1.5 rounded hover:bg-gray-50 text-xs flex items-center justify-between"
                      >
                        <span className="text-gray-800 truncate max-w-[140px]">{n.label}</span>
                        <span className={`font-medium ${
                          buyVal > 0 && sellVal === 0 ? 'text-green-600' :
                          sellVal > 0 && buyVal === 0 ? 'text-red-600' :
                          role ? 'text-blue-500' :
                          'text-gray-400'
                        }`}>
                          {buyVal > 0 ? formatValue(buyVal) :
                           sellVal > 0 ? formatValue(sellVal) :
                           role || ''}
                        </span>
                      </button>
                    )
                  })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !graphData && !query && (
        <div className="bg-gray-50 rounded-2xl p-16 text-center">
          <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <p className="text-gray-500 text-lg">
            {mode === 'company'
              ? 'Search for a company to explore its insider network'
              : 'Search for a person to see all their trading connections'}
          </p>
          <p className="text-gray-400 text-sm mt-2">
            Try: {mode === 'company' ? 'FMBM, NXST, STIM, BAC, GS' : 'Chernett Jorey, Chang Carmen'}
          </p>
        </div>
      )}
    </div>
  )
}
