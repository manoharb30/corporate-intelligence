import { useState } from 'react'
import { companiesApi, personsApi, Company, Person } from '../services/api'
import EntityCard from '../components/EntityCard'
import SearchBar from '../components/SearchBar'

type SearchResults = {
  companies: Company[]
  persons: Person[]
}

export default function Search() {
  const [results, setResults] = useState<SearchResults | null>(null)
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')

  const handleSearch = async (searchQuery: string) => {
    setQuery(searchQuery)
    setLoading(true)
    try {
      const [companiesRes, personsRes] = await Promise.all([
        companiesApi.search(searchQuery, 10),
        personsApi.search(searchQuery, 10),
      ])
      setResults({
        companies: companiesRes.data,
        persons: personsRes.data,
      })
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setLoading(false)
    }
  }

  const getBadges = (person: Person) => {
    const badges: Array<{ label: string; color: 'red' | 'yellow' | 'green' | 'blue' | 'gray' }> = []
    if (person.is_pep) badges.push({ label: 'PEP', color: 'yellow' })
    if (person.is_sanctioned) badges.push({ label: 'Sanctioned', color: 'red' })
    return badges
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Search</h1>
        <p className="mt-1 text-sm text-gray-600">
          Search for companies and persons across the graph
        </p>
      </div>

      <div className="mb-8">
        <SearchBar
          onSearch={handleSearch}
          placeholder="Search companies and persons..."
        />
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          <p className="mt-2 text-sm text-gray-500">Searching...</p>
        </div>
      ) : results ? (
        <div>
          {query && (
            <p className="text-sm text-gray-600 mb-6">
              Results for "{query}"
            </p>
          )}

          {/* Companies */}
          <div className="mb-8">
            <h2 className="text-lg font-medium text-gray-900 mb-4">
              Companies ({results.companies.length})
            </h2>
            {results.companies.length > 0 ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {results.companies.map((company) => (
                  <EntityCard
                    key={company.id}
                    id={company.id}
                    name={company.name}
                    type="company"
                    subtitle={company.jurisdiction ? `Jurisdiction: ${company.jurisdiction}` : undefined}
                  />
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">No companies found</p>
            )}
          </div>

          {/* Persons */}
          <div>
            <h2 className="text-lg font-medium text-gray-900 mb-4">
              Persons ({results.persons.length})
            </h2>
            {results.persons.length > 0 ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {results.persons.map((person) => (
                  <EntityCard
                    key={person.id}
                    id={person.id}
                    name={person.name}
                    type="person"
                    badges={getBadges(person)}
                  />
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">No persons found</p>
            )}
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-gray-500">
          <p>Enter a search query to find companies and persons</p>
        </div>
      )}
    </div>
  )
}
