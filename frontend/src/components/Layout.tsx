import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import AlertBell from './AlertBell'

interface LayoutProps {
  children: ReactNode
}

const navigation = [
  { name: 'Dashboard', href: '/' },
  { name: 'Signals', href: '/signals' },
  { name: 'Track Record', href: '/accuracy' },
  { name: 'Companies', href: '/companies' },
  { name: 'Network', href: '/network' },
  { name: 'Pricing', href: '/pricing' },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  const isActive = (href: string) => {
    if (href === '/') return location.pathname === '/'
    return location.pathname.startsWith(href)
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
