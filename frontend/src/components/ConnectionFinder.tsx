import { useState, useEffect, useRef } from 'react'
import { companiesApi, personsApi, Company, Person } from '../services/api'

type Entity = (Company | Person) & { entityType: 'company' | 'person' }

interface ConnectionFinderProps {
  onSearch: (entityA: string, entityB: string, maxHops: number) => void
  isLoading?: boolean
  initialEntityA?: { id: string; name: string }
  initialEntityB?: { id: string; name: string }
}

function EntitySearch({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string
  value: { id: string; name: string } | null
  onChange: (entity: { id: string; name: string } | null) => void
  placeholder: string
}) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Entity[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (query.length < 2) {
      setResults([])
      return
    }

    const search = async () => {
      setIsLoading(true)
      try {
        const [companiesRes, personsRes] = await Promise.all([
          companiesApi.search(query, 5),
          personsApi.search(query, 5),
        ])

        const companies: Entity[] = companiesRes.data.map(c => ({ ...c, entityType: 'company' as const }))
        const persons: Entity[] = personsRes.data.map(p => ({ ...p, entityType: 'person' as const }))

        setResults([...companies, ...persons])
      } catch (error) {
        console.error('Search error:', error)
      } finally {
        setIsLoading(false)
      }
    }

    const debounce = setTimeout(search, 300)
    return () => clearTimeout(debounce)
  }, [query])

  const handleSelect = (entity: Entity) => {
    onChange({ id: entity.id, name: entity.name })
    setQuery('')
    setIsOpen(false)
  }

  const handleClear = () => {
    onChange(null)
    setQuery('')
  }

  return (
    <div ref={wrapperRef} className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>

      {value ? (
        <div className="flex items-center justify-between px-3 py-2 border border-gray-300 rounded-md bg-gray-50">
          <span className="text-sm text-gray-900">{value.name}</span>
          <button
            onClick={handleClear}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ) : (
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setIsOpen(true)
            }}
            onFocus={() => setIsOpen(true)}
            placeholder={placeholder}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500"
          />
          {isLoading && (
            <div className="absolute right-3 top-2.5">
              <div className="animate-spin h-4 w-4 border-2 border-primary-500 rounded-full border-t-transparent"></div>
            </div>
          )}
        </div>
      )}

      {isOpen && results.length > 0 && !value && (
        <div className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto">
          {results.map((entity) => (
            <button
              key={entity.id}
              onClick={() => handleSelect(entity)}
              className="w-full px-3 py-2 text-left hover:bg-gray-100 flex items-center space-x-2"
            >
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                entity.entityType === 'company' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
              }`}>
                {entity.entityType === 'company' ? 'Company' : 'Person'}
              </span>
              <span className="text-sm text-gray-900">{entity.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ConnectionFinder({
  onSearch,
  isLoading = false,
  initialEntityA,
  initialEntityB,
}: ConnectionFinderProps) {
  const [entityA, setEntityA] = useState<{ id: string; name: string } | null>(initialEntityA || null)
  const [entityB, setEntityB] = useState<{ id: string; name: string } | null>(initialEntityB || null)
  const [maxHops, setMaxHops] = useState(4)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (entityA && entityB) {
      onSearch(entityA.id, entityB.id, maxHops)
    }
  }

  const canSearch = entityA && entityB && entityA.id !== entityB.id

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Find Connection</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <EntitySearch
          label="From Entity"
          value={entityA}
          onChange={setEntityA}
          placeholder="Search companies or persons..."
        />
        <EntitySearch
          label="To Entity"
          value={entityB}
          onChange={setEntityB}
          placeholder="Search companies or persons..."
        />
      </div>

      <div className="flex items-end space-x-4">
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Max Hops
          </label>
          <select
            value={maxHops}
            onChange={(e) => setMaxHops(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500"
          >
            <option value={2}>2 hops</option>
            <option value={3}>3 hops</option>
            <option value={4}>4 hops (default)</option>
            <option value={5}>5 hops</option>
            <option value={6}>6 hops</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={!canSearch || isLoading}
          className={`px-6 py-2 rounded-md font-medium transition-colors ${
            canSearch && !isLoading
              ? 'bg-primary-600 text-white hover:bg-primary-700'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
        >
          {isLoading ? (
            <span className="flex items-center space-x-2">
              <div className="animate-spin h-4 w-4 border-2 border-white rounded-full border-t-transparent"></div>
              <span>Searching...</span>
            </span>
          ) : (
            'Find Connection'
          )}
        </button>
      </div>

      {entityA && entityB && entityA.id === entityB.id && (
        <p className="mt-2 text-sm text-red-600">Please select two different entities.</p>
      )}
    </form>
  )
}
