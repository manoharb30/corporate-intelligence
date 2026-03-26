import { ReactNode } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import AlertBell from './AlertBell'

interface LayoutProps {
  children: ReactNode
}

const navigation = [
  { name: 'Dashboard', href: '/' },
  { name: 'Trade Signals', href: '/signals?tab=trade' },
  { name: 'Intelligence', href: '/signals?tab=intelligence' },
  { name: 'Snapshot', href: '/snapshot' },
  { name: 'Accuracy', href: '/accuracy' },
  { name: 'Track Record', href: '/track-record' },
  { name: 'Research', href: '/blog/insider-signal-research' },
  { name: 'Pricing', href: '/pricing' },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  const [searchParams] = useSearchParams()

  const isActive = (href: string) => {
    if (href === '/') return location.pathname === '/'
    const [path, query] = href.split('?')
    if (!location.pathname.startsWith(path)) return false
    if (query) {
      const params = new URLSearchParams(query)
      for (const [key, value] of params) {
        if (searchParams.get(key) !== value) return false
      }
      return true
    }
    // For plain paths like /accuracy, /companies — match if no tab param
    if (path === '/signals') return false // /signals without tab shouldn't match
    return true
  }

  return (
    <div className="min-h-screen">
      <nav className="bg-primary-800">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center">
              <Link to="/" className="flex-shrink-0">
                <span className="text-white text-xl font-bold">
                  Corporate Intelligence
                </span>
              </Link>
              <div className="hidden md:block">
                <div className="ml-10 flex items-baseline space-x-4">
                  {navigation.map((item) => (
                    <Link
                      key={item.name}
                      to={item.href}
                      className={`${
                        isActive(item.href)
                          ? 'bg-primary-900 text-white'
                          : 'text-gray-300 hover:bg-primary-700 hover:text-white'
                      } rounded-md px-3 py-2 text-sm font-medium`}
                    >
                      {item.name}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex items-center">
              <AlertBell />
            </div>
          </div>
        </div>
      </nav>

      <main>
        <div className="mx-auto max-w-7xl py-6 px-4 sm:px-6 lg:px-8">
          {children}
        </div>
      </main>
    </div>
  )
}
