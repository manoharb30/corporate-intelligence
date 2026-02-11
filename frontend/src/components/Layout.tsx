import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

interface LayoutProps {
  children: ReactNode
}

const navigation = [
  { name: 'Overview', href: '/dashboard' },
  { name: 'Signal Feed', href: '/' },
  { name: 'Intelligence', href: '/intelligence' },
  { name: 'Companies', href: '/companies' },
  { name: 'Connections', href: '/connections' },
  { name: 'Graph Explorer', href: '/graph' },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  return (
    <div className="min-h-screen">
      <nav className="bg-primary-800">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <span className="text-white text-xl font-bold">
                  Corporate Intelligence
                </span>
              </div>
              <div className="hidden md:block">
                <div className="ml-10 flex items-baseline space-x-4">
                  {navigation.map((item) => {
                    const isActive = location.pathname === item.href
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={`${
                          isActive
                            ? 'bg-primary-900 text-white'
                            : 'text-gray-300 hover:bg-primary-700 hover:text-white'
                        } rounded-md px-3 py-2 text-sm font-medium`}
                      >
                        {item.name}
                      </Link>
                    )
                  })}
                </div>
              </div>
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
