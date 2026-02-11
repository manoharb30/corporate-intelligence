import { Link } from 'react-router-dom'

interface EntityCardProps {
  id: string
  name: string
  type: 'company' | 'person'
  subtitle?: string
  badges?: Array<{ label: string; color: 'red' | 'yellow' | 'green' | 'blue' | 'gray' }>
}

const badgeColors = {
  red: 'bg-red-100 text-red-800',
  yellow: 'bg-yellow-100 text-yellow-800',
  green: 'bg-green-100 text-green-800',
  blue: 'bg-blue-100 text-blue-800',
  gray: 'bg-gray-100 text-gray-800',
}

export default function EntityCard({ id, name, type, subtitle, badges = [] }: EntityCardProps) {
  const href = type === 'company' ? `/companies/${id}` : `/persons/${id}`

  return (
    <Link
      to={href}
      className="block bg-white rounded-lg shadow hover:shadow-md transition-shadow p-4"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-medium text-gray-900">{name}</h3>
          {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
        </div>
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
          type === 'company' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
        }`}>
          {type === 'company' ? 'Company' : 'Person'}
        </span>
      </div>
      {badges.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {badges.map((badge, idx) => (
            <span
              key={idx}
              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${badgeColors[badge.color]}`}
            >
              {badge.label}
            </span>
          ))}
        </div>
      )}
    </Link>
  )
}
