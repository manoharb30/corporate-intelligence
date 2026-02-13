import { useEffect, useRef, useState, useCallback } from 'react'
import ForceGraph2D, { NodeObject, LinkObject } from 'react-force-graph-2d'
import { graphApi } from '../services/api'

interface MiniGraphProps {
  entityId: string
  height?: number
  depth?: number
}

interface GraphNode extends NodeObject {
  id: string
  label: string
  type: string
}

interface GraphLink extends LinkObject {
  type: string
}

const TYPE_COLORS: Record<string, string> = {
  Company: '#6366f1',
  Person: '#10b981',
  Event: '#f59e0b',
  InsiderTransaction: '#ef4444',
}

export default function MiniGraph({ entityId, height = 300, depth = 1 }: MiniGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({ nodes: [], links: [] })
  const [width, setWidth] = useState(400)

  useEffect(() => {
    if (!entityId) return
    graphApi.getEntityGraph(entityId, depth, false)
      .then(res => {
        const data = res.data
        setGraphData({
          nodes: data.nodes.map(n => ({ id: n.id, label: n.label, type: n.type })),
          links: data.edges.map(e => ({ source: e.source, target: e.target, type: e.type })),
        })
      })
      .catch(() => setGraphData({ nodes: [], links: [] }))
  }, [entityId, depth])

  useEffect(() => {
    if (containerRef.current) {
      setWidth(containerRef.current.clientWidth)
    }
    const handleResize = () => {
      if (containerRef.current) setWidth(containerRef.current.clientWidth)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const nodeCanvasObject = useCallback((node: GraphNode, ctx: CanvasRenderingContext2D) => {
    const x = node.x ?? 0
    const y = node.y ?? 0
    const color = TYPE_COLORS[node.type] || '#9ca3af'
    const radius = 6

    ctx.beginPath()
    ctx.arc(x, y, radius, 0, 2 * Math.PI)
    ctx.fillStyle = color
    ctx.fill()

    ctx.font = '3px Inter, sans-serif'
    ctx.textAlign = 'center'
    ctx.fillStyle = '#374151'
    const label = node.label.length > 20 ? node.label.slice(0, 18) + '...' : node.label
    ctx.fillText(label, x, y + radius + 5)
  }, [])

  if (graphData.nodes.length === 0) {
    return (
      <div ref={containerRef} className="flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200 text-gray-400 text-sm" style={{ height }}>
        No graph data
      </div>
    )
  }

  return (
    <div ref={containerRef} className="rounded-lg overflow-hidden border border-gray-200 bg-white">
      <ForceGraph2D
        graphData={graphData}
        width={width}
        height={height}
        nodeCanvasObject={nodeCanvasObject as any}
        linkColor={() => '#d1d5db'}
        linkWidth={1}
        enableZoomInteraction={false}
        enablePanInteraction={false}
        cooldownTicks={50}
      />
    </div>
  )
}
