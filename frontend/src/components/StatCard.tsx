interface StatCardProps {
  label: string
  value: string | number
  subtitle?: string
  accent?: string // tailwind color class
}

export default function StatCard({ label, value, subtitle, accent = 'text-primary-600' }: StatCardProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500 font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${accent}`}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
    </div>
  )
}
