import { useEffect, useState } from 'react'
import { companiesApi, Company, PaginatedResponse } from '../services/api'
import EntityCard from '../components/EntityCard'
import SearchBar from '../components/SearchBar'

export default function Companies() {
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [searchResults, setSearchResults] = useState<Company[] | null>(null)

  useEffect(() => {
    loadCompanies()
  }, [page])

  const loadCompanies = async () => {
    setLoading(true)
    try {
      const response = await companiesApi.list(page, 20)
      const data = response.data as PaginatedResponse<Company>
      setCompanies(data.items)
      setTotalPages(data.pages)
    } catch (error) {
      console.error('Failed to load companies:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async (query: string) => {
    try {
      const response = await companiesApi.search(query, 20)
      setSearchResults(response.data)
    } catch (error) {
      console.error('Search failed:', error)
    }
  }

  const clearSearch = () => {
    setSearchResults(null)
  }

  const displayCompanies = searchResults ?? companies

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Companies</h1>
        <p className="mt-1 text-sm text-gray-600">
          Browse and search companies in the graph
        </p>
      </div>

      <div className="mb-6 flex items-center gap-4">
        <SearchBar onSearch={handleSearch} placeholder="Search companies..." />
        {searchResults && (
          <button
            onClick={clearSearch}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Clear search
          </button>
        )}
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          <p className="mt-2 text-sm text-gray-500">Loading companies...</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {displayCompanies.map((company) => (
              <EntityCard
                key={company.id}
                id={company.id}
                name={company.name}
                type="company"
                subtitle={company.jurisdiction ? `Jurisdiction: ${company.jurisdiction}` : undefined}
                badges={company.status ? [{ label: company.status, color: 'blue' }] : []}
              />
            ))}
          </div>

          {!searchResults && totalPages > 1 && (
            <div className="mt-6 flex items-center justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1 rounded border border-gray-300 disabled:opacity-50"
              >
                Previous
              </button>
              <span className="text-sm text-gray-600">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1 rounded border border-gray-300 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
