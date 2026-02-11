import { useEffect, useState } from 'react'
import { personsApi, Person, PaginatedResponse } from '../services/api'
import EntityCard from '../components/EntityCard'
import SearchBar from '../components/SearchBar'

export default function Persons() {
  const [persons, setPersons] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [searchResults, setSearchResults] = useState<Person[] | null>(null)
  const [filter, setFilter] = useState<'all' | 'pep' | 'sanctioned'>('all')

  useEffect(() => {
    loadPersons()
  }, [page, filter])

  const loadPersons = async () => {
    setLoading(true)
    try {
      let response
      if (filter === 'pep') {
        response = await personsApi.listPeps(50)
        setPersons(response.data)
        setTotalPages(1)
      } else if (filter === 'sanctioned') {
        response = await personsApi.listSanctioned(50)
        setPersons(response.data)
        setTotalPages(1)
      } else {
        response = await personsApi.list(page, 20)
        const data = response.data as PaginatedResponse<Person>
        setPersons(data.items)
        setTotalPages(data.pages)
      }
    } catch (error) {
      console.error('Failed to load persons:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async (query: string) => {
    try {
      const response = await personsApi.search(query, 20)
      setSearchResults(response.data)
    } catch (error) {
      console.error('Search failed:', error)
    }
  }

  const clearSearch = () => {
    setSearchResults(null)
  }

  const displayPersons = searchResults ?? persons

  const getBadges = (person: Person) => {
    const badges: Array<{ label: string; color: 'red' | 'yellow' | 'green' | 'blue' | 'gray' }> = []
    if (person.is_pep) badges.push({ label: 'PEP', color: 'yellow' })
    if (person.is_sanctioned) badges.push({ label: 'Sanctioned', color: 'red' })
    return badges
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Persons</h1>
        <p className="mt-1 text-sm text-gray-600">
          Browse and search persons in the graph
        </p>
      </div>

      <div className="mb-6 flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <SearchBar onSearch={handleSearch} placeholder="Search persons..." />
        {searchResults && (
          <button
            onClick={clearSearch}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Clear search
          </button>
        )}
      </div>

      {!searchResults && (
        <div className="mb-6 flex gap-2">
          <button
            onClick={() => { setFilter('all'); setPage(1) }}
            className={`px-3 py-1 rounded text-sm ${
              filter === 'all'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            All
          </button>
          <button
            onClick={() => { setFilter('pep'); setPage(1) }}
            className={`px-3 py-1 rounded text-sm ${
              filter === 'pep'
                ? 'bg-yellow-500 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            PEPs
          </button>
          <button
            onClick={() => { setFilter('sanctioned'); setPage(1) }}
            className={`px-3 py-1 rounded text-sm ${
              filter === 'sanctioned'
                ? 'bg-red-500 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Sanctioned
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          <p className="mt-2 text-sm text-gray-500">Loading persons...</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {displayPersons.map((person) => (
              <EntityCard
                key={person.id}
                id={person.id}
                name={person.name}
                type="person"
                badges={getBadges(person)}
              />
            ))}
          </div>

          {!searchResults && filter === 'all' && totalPages > 1 && (
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
