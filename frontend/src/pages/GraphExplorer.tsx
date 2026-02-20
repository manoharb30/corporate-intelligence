import { useState, useRef, useEffect, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { graphApi, profileApi, GraphData, ProfileSearchResult } from '../services/api'
import { Link } from 'react-router-dom'

interface ForceNode {
  id: string
  name: string
  type: string
  val: number
  color: string
}

interface ForceLink {
  source: string
  target: string
  type: string
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
}

function transformGraphData(data: GraphData): ForceGraphData {
  const nodes: ForceNode[] = data.nodes.map((node) => ({
    id: node.id,
    name: node.label || node.properties?.name as string || node.id,
    type: node.type,
    val: node.type === 'Company' ? 20 : 12,
    color: NODE_COLORS[node.type] || '#6b7280',
  }))

  const nodeIds = new Set(nodes.map(n => n.id))
  const links: ForceLink[] = data.edges
    .filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .map((edge) => ({
      source: edge.source,
      target: edge.target,
      type: edge.type,
    }))

  return { nodes, links }
}

export default function GraphExplorer() {
  const [graphData, setGraphData] = useState<ForceGraphData>({ nodes: [], links: [] })
  const [rawData, setRawData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(false)
  const [entityId, setEntityId] = useState('')
  const [depth, setDepth] = useState(2)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ProfileSearchResult[]>([])
  const [selectedNode, setSelectedNode] = useState<ForceNode | null>(null)
  const graphRef = useRef<any>()

  // Search companies
  useEffect(() => {
    if (searchQuery.length >= 2) {
      const timer = setTimeout(async () => {
        try {
          const response = await profileApi.searchCompanies(searchQuery, 8)
          setSearchResults(response.data.results)
        } catch {
          setSearchResults([])
        }
      }, 300)
      return () => clearTimeout(timer)
    } else {
      setSearchResults([])
    }
  }, [searchQuery])

  // Zoom to fit on data change
  useEffect(() => {
    if (graphRef.current && graphData.nodes.length > 0) {
      setTimeout(() => {
        graphRef.current.zoomToFit(400, 50)
      }, 500)
    }
  }, [graphData])

  const loadGraph = async (id?: string) => {
    const targetId = id || entityId
    if (!targetId) return
    setLoading(true)
    setSelectedNode(null)
    try {
      const response = await graphApi.getEntityGraph(targetId, depth)
      setRawData(response.data)
      setGraphData(transformGraphData(response.data))
    } catch (error) {
      console.error('Failed to load graph:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadOwnershipGraph = async (direction: 'up' | 'down' | 'both') => {
    if (!entityId) return
    setLoading(true)
    setSelectedNode(null)
    try {
      const response = await graphApi.getOwnershipGraph(entityId, direction, 5)
      setRawData(response.data)
      setGraphData(transformGraphData(response.data))
    } catch (error) {
      console.error('Failed to load ownership graph:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectCompany = (result: ProfileSearchResult) => {
    // Use CIK to find the company node - we need to search by CIK in graph
    setSearchQuery('')
    setSearchResults([])
    setEntityId(result.cik)
    // Load graph using CIK - the graph API should handle this
    loadGraph(result.cik)
  }

  const handleNodeClick = useCallback((node: any) => {
    setSelectedNode(node as ForceNode)
  }, [])

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col">
      {/* Header + Search */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Graph Explorer</h1>
        <p className="mt-1 text-sm text-gray-600">
          Explore ownership structures and entity relationships
        </p>
      </div>

      <div className="bg-white shadow rounded-lg p-4 mb-4">
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-end">
          {/* Company Search */}
          <div className="flex-1 relative">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search Company
            </label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by company name or ticker..."
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm border px-3 py-2"
            />
            {searchResults.length > 0 && (
              <div className="absolute z-20 w-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 max-h-60 overflow-y-auto">
                {searchResults.map((result) => (
                  <button
                    key={result.cik}
                    onClick={() => handleSelectCompany(result)}
                    className="block w-full text-left px-4 py-2 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
                  >
                    <span className="font-medium text-gray-900">{result.name}</span>
                    {result.ticker && <span className="ml-2 text-sm text-gray-500">({result.ticker})</span>}
                    <span className="ml-2 text-xs text-gray-400">{result.signal_count} signals</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Manual Entity ID */}
          <div className="w-48">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Entity ID
            </label>
            <input
              type="text"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              placeholder="CIK or node ID..."
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm border px-3 py-2"
            />
          </div>

          <div className="w-20">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Depth
            </label>
            <select
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm border px-3 py-2"
            >
              {[1, 2, 3, 4, 5].map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>

          <button
            onClick={() => loadGraph()}
            disabled={!entityId || loading}
            className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Load Graph'}
          </button>
        </div>

        <div className="mt-3 flex gap-2">
          <button
            onClick={() => loadOwnershipGraph('up')}
            disabled={!entityId || loading}
            className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
          >
            Owners (Up)
          </button>
          <button
            onClick={() => loadOwnershipGraph('down')}
            disabled={!entityId || loading}
            className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
          >
            Subsidiaries (Down)
          </button>
          <button
            onClick={() => loadOwnershipGraph('both')}
            disabled={!entityId || loading}
            className="px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 disabled:opacity-50"
          >
            Full Structure
          </button>
          {rawData && (
            <span className="ml-auto text-sm text-gray-500 self-center">
              {rawData.nodes.length} nodes, {rawData.edges.length} edges
            </span>
          )}
        </div>
      </div>

      {/* Graph Area */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center bg-gray-900 rounded-lg">
          <div className="text-center">
            <div className="animate-spin h-10 w-10 border-4 border-blue-400 border-t-transparent rounded-full mx-auto mb-3"></div>
            <p className="text-gray-400">Loading graph...</p>
          </div>
        </div>
      ) : graphData.nodes.length > 0 ? (
        <div className="flex-1 bg-gray-900 rounded-lg relative overflow-hidden">
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            nodeLabel={(node: any) => `${node.name} (${node.type})`}
            nodeRelSize={6}
            linkColor={() => '#4b5563'}
            linkWidth={1.5}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={0.9}
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              const label = node.name || ''
              const fontSize = Math.max(10 / globalScale, 2)
              ctx.font = `${fontSize}px Sans-Serif`

              // Draw node circle
              const size = (node.val || 10) / 2
              ctx.beginPath()
              ctx.arc(node.x, node.y, size, 0, 2 * Math.PI)
              ctx.fillStyle = node.color
              ctx.fill()

              // Highlight selected node
              if (selectedNode && selectedNode.id === node.id) {
                ctx.strokeStyle = '#ffffff'
                ctx.lineWidth = 2 / globalScale
                ctx.stroke()
              }

              // Draw label
              if (globalScale > 0.5) {
                ctx.textAlign = 'center'
                ctx.textBaseline = 'middle'
                ctx.fillStyle = '#e5e7eb'
                const truncated = label.length > 20 ? label.substring(0, 17) + '...' : label
                ctx.fillText(truncated, node.x, node.y + size + fontSize)
              }
            }}
            nodePointerAreaPaint={(node: any, color, ctx) => {
              const size = (node.val || 10) / 2
              ctx.beginPath()
              ctx.arc(node.x, node.y, size + 4, 0, 2 * Math.PI)
              ctx.fillStyle = color
              ctx.fill()
            }}
            onNodeClick={handleNodeClick}
          />

          {/* Legend */}
          <div className="absolute top-3 left-3 bg-white/90 p-3 rounded-lg text-sm">
            <div className="font-semibold mb-2">Legend</div>
            {Object.entries(NODE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-2 mb-1">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: color }}></span>
                <span>{type}</span>
              </div>
            ))}
          </div>

          {/* Selected Node Info */}
          {selectedNode && (
            <div className="absolute top-3 right-3 bg-white/95 p-4 rounded-lg max-w-xs shadow-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="px-2 py-0.5 rounded text-xs font-medium text-white" style={{ backgroundColor: selectedNode.color }}>
                  {selectedNode.type}
                </span>
                <button onClick={() => setSelectedNode(null)} className="text-gray-400 hover:text-gray-600 text-lg font-bold">
                  x
                </button>
              </div>
              <h3 className="font-semibold text-gray-900 text-sm">{selectedNode.name}</h3>
              <p className="text-xs text-gray-500 mt-1">ID: {selectedNode.id}</p>
              {selectedNode.type === 'Company' && (
                <Link
                  to={`/signals?cik=${selectedNode.id}`}
                  className="mt-2 block text-xs text-primary-600 hover:underline"
                >
                  View Company Signals
                </Link>
              )}
              <button
                onClick={() => {
                  setEntityId(selectedNode.id)
                  loadGraph(selectedNode.id)
                }}
                className="mt-2 px-3 py-1 text-xs bg-primary-600 text-white rounded hover:bg-primary-700 w-full"
              >
                Explore from here
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <div className="text-center text-gray-500">
            <p className="text-lg mb-2">Search for a company or enter an entity ID</p>
            <p className="text-sm">Click "Load Graph" to visualize the corporate network</p>
          </div>
        </div>
      )}
    </div>
  )
}
