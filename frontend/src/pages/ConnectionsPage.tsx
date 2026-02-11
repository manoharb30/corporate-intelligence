import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { connectionsApi, ConnectionClaim } from '../services/api'
import ConnectionFinder from '../components/ConnectionFinder'
import ConnectionResult from '../components/ConnectionResult'

export default function ConnectionsPage() {
  const [searchParams] = useSearchParams()
  const [connection, setConnection] = useState<ConnectionClaim | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchHistory, setSearchHistory] = useState<Array<{
    entityA: string
    entityAName: string
    entityB: string
    entityBName: string
    result: ConnectionClaim | null
    error: string | null
  }>>([])

  // Get initial entity from URL params (from Company Detail page)
  const initialFromId = searchParams.get('from')
  const initialFromName = searchParams.get('fromName')

  const initialEntityA = initialFromId && initialFromName
    ? { id: initialFromId, name: initialFromName }
    : undefined

  const handleSearch = async (entityAId: string, entityBId: string, maxHops: number) => {
    setIsLoading(true)
    setError(null)
    setConnection(null)

    try {
      const res = await connectionsApi.findConnection(entityAId, entityBId, maxHops)
      setConnection(res.data)

      // Add to history
      setSearchHistory(prev => [{
        entityA: entityAId,
        entityAName: res.data.entity_a_name,
        entityB: entityBId,
        entityBName: res.data.entity_b_name,
        result: res.data,
        error: null,
      }, ...prev.slice(0, 9)])
    } catch (err: unknown) {
      const errorMessage = err instanceof Error
        ? err.message
        : (err as { response?: { status?: number } })?.response?.status === 404
          ? 'No connection found between these entities within the specified hops.'
          : 'Failed to find connection. Please try again.'

      setError(errorMessage)

      // Add failed search to history
      setSearchHistory(prev => [{
        entityA: entityAId,
        entityAName: entityAId,
        entityB: entityBId,
        entityBName: entityBId,
        result: null,
        error: errorMessage,
      }, ...prev.slice(0, 9)])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Connection Explorer</h1>
        <p className="text-gray-600 mt-1">
          Find and trace connections between entities with full evidence chains.
        </p>
      </div>

      {/* Search Form */}
      <div className="mb-6">
        <ConnectionFinder
          onSearch={handleSearch}
          isLoading={isLoading}
          initialEntityA={initialEntityA}
        />
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center">
            <svg className="w-5 h-5 text-red-500 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-red-700">{error}</span>
          </div>
        </div>
      )}

      {/* Connection Result */}
      {connection && (
        <div className="mb-6">
          <ConnectionResult connection={connection} />
        </div>
      )}

      {/* Search History */}
      {searchHistory.length > 0 && !connection && !isLoading && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Searches</h2>
          <div className="space-y-3">
            {searchHistory.map((item, index) => (
              <div
                key={index}
                className={`p-3 rounded-lg border ${
                  item.result ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="font-medium text-gray-900">{item.entityAName}</span>
                    <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
                    </svg>
                    <span className="font-medium text-gray-900">{item.entityBName}</span>
                  </div>
                  {item.result ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                      {item.result.path_length} hop{item.result.path_length !== 1 ? 's' : ''}
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                      Not found
                    </span>
                  )}
                </div>
                {item.result && (
                  <button
                    onClick={() => setConnection(item.result)}
                    className="mt-2 text-sm text-primary-600 hover:text-primary-800"
                  >
                    View result
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!connection && !isLoading && !error && searchHistory.length === 0 && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">Find Hidden Connections</h3>
          <p className="text-gray-500 max-w-md mx-auto">
            Search for connections between any two entities. The system will find the shortest path
            and provide evidence for each step in the chain.
          </p>
        </div>
      )}
    </div>
  )
}
