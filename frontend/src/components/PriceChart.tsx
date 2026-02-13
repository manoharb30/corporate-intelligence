import { useEffect, useRef, useState } from 'react'
import { createChart, createSeriesMarkers, AreaSeries, IChartApi, LineData, Time } from 'lightweight-charts'
import { stockPriceApi, StockPriceData } from '../services/api'

export interface ChartMarker {
  date: string
  label: string
  color: string
  shape: 'circle' | 'arrowUp' | 'arrowDown' | 'square'
  position: 'aboveBar' | 'belowBar'
}

interface PriceChartProps {
  ticker: string
  period?: string
  height?: number
  markers?: ChartMarker[]
  onPeriodChange?: (period: string) => void
  showPeriodSelector?: boolean
  onMarkerClick?: (marker: ChartMarker) => void
}

export default function PriceChart({
  ticker,
  period = '1y',
  height = 350,
  markers = [],
  onPeriodChange,
  showPeriodSelector = true,
  onMarkerClick,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const markersRef = useRef<ChartMarker[]>(markers)
  const onMarkerClickRef = useRef(onMarkerClick)
  const [prices, setPrices] = useState<StockPriceData[]>([])
  const [loading, setLoading] = useState(true)
  const [activePeriod, setActivePeriod] = useState(period)

  // Keep refs in sync
  markersRef.current = markers
  onMarkerClickRef.current = onMarkerClick

  useEffect(() => {
    if (!ticker) return
    setLoading(true)
    stockPriceApi.getPrice(ticker, activePeriod)
      .then(res => setPrices(res.data.prices))
      .catch(() => setPrices([]))
      .finally(() => setLoading(false))
  }, [ticker, activePeriod])

  useEffect(() => {
    if (!containerRef.current || prices.length === 0) return

    // Clean up previous chart
    if (chartRef.current) {
      chartRef.current.remove()
      chartRef.current = null
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#6b7280',
        fontFamily: 'Inter, system-ui, sans-serif',
      },
      grid: {
        vertLines: { color: '#f3f4f6' },
        horzLines: { color: '#f3f4f6' },
      },
      rightPriceScale: {
        borderColor: '#e5e7eb',
      },
      timeScale: {
        borderColor: '#e5e7eb',
        timeVisible: false,
      },
      crosshair: {
        vertLine: { color: '#6366f1', width: 1, style: 2 },
        horzLine: { color: '#6366f1', width: 1, style: 2 },
      },
    })
    chartRef.current = chart

    const series = chart.addSeries(AreaSeries, {
      lineColor: '#6366f1',
      topColor: 'rgba(99, 102, 241, 0.3)',
      bottomColor: 'rgba(99, 102, 241, 0.02)',
      lineWidth: 2,
    })

    const lineData: LineData[] = prices.map(p => ({
      time: p.date as Time,
      value: p.close,
    }))
    series.setData(lineData)

    // Add markers
    const priceMap = new Map(prices.map(p => [p.date, p]))
    const markerDates = new Set<string>()
    if (markers.length > 0) {
      const validMarkers = markers
        .filter(m => priceMap.has(m.date))
        .sort((a, b) => a.date.localeCompare(b.date))
        .map(m => {
          markerDates.add(m.date)
          return {
            time: m.date as Time,
            position: m.position,
            color: m.color,
            shape: m.shape,
            text: m.label,
          }
        })
      if (validMarkers.length > 0) {
        createSeriesMarkers(series, validMarkers)
      }
    }

    // Click handler — detect clicks on or near marker dates
    chart.subscribeClick((param) => {
      if (!param.time || !onMarkerClickRef.current) return
      const clickedDate = param.time as string
      // Find the marker that matches this date
      const matched = markersRef.current.find(m => m.date === clickedDate)
      if (matched) {
        onMarkerClickRef.current(matched)
      }
    })

    chart.timeScale().fitContent()

    // Resize handler
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
    }
  }, [prices, markers, height])

  const handlePeriodChange = (p: string) => {
    setActivePeriod(p)
    onPeriodChange?.(p)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200" style={{ height }}>
        <div className="animate-spin h-6 w-6 border-2 border-primary-500 border-t-transparent rounded-full"></div>
      </div>
    )
  }

  if (prices.length === 0) {
    return (
      <div className="flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200 text-gray-400 text-sm" style={{ height: height / 2 }}>
        No price data available for {ticker}
      </div>
    )
  }

  return (
    <div>
      {showPeriodSelector && (
        <div className="flex gap-1 mb-2">
          {['3mo', '6mo', '1y', '2y'].map(p => (
            <button
              key={p}
              onClick={() => handlePeriodChange(p)}
              className={`px-3 py-1 text-xs font-medium rounded ${
                activePeriod === p
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {p.toUpperCase()}
            </button>
          ))}
        </div>
      )}
      <div ref={containerRef} className="rounded-lg overflow-hidden border border-gray-200 cursor-pointer" />
    </div>
  )
}
