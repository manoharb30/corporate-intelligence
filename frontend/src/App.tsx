import { Routes, Route, Navigate, useParams } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Feed from './pages/Feed'
import SignalStory from './pages/SignalStory'
import Companies from './pages/Companies'
import CompanyDetail from './pages/CompanyDetail'
import NetworkPage from './pages/NetworkPage'
import Pricing from './pages/Pricing'

/** Redirect /company/:cik to /signals?cik=:cik */
function CompanyRedirect() {
  const { cik } = useParams<{ cik: string }>()
  return <Navigate to={`/signals?cik=${cik}`} replace />
}

function App() {
  return (
    <Layout>
      <Routes>
        {/* Primary routes */}
        <Route path="/" element={<Dashboard />} />
        <Route path="/signals" element={<Feed />} />
        <Route path="/signal/:accessionNumber" element={<SignalStory />} />
        <Route path="/companies" element={<Companies />} />
        <Route path="/companies/:id" element={<CompanyDetail />} />
        <Route path="/network" element={<NetworkPage />} />
        <Route path="/pricing" element={<Pricing />} />

        {/* Redirects for old routes */}
        <Route path="/company/:cik" element={<CompanyRedirect />} />
        <Route path="/dashboard" element={<Navigate to="/" replace />} />
        <Route path="/event/:accessionNumber" element={<Navigate to="/signal/:accessionNumber" replace />} />
        <Route path="/intelligence" element={<Navigate to="/network" replace />} />
        <Route path="/graph" element={<Navigate to="/network" replace />} />
        <Route path="/connections" element={<Navigate to="/network" replace />} />
        <Route path="/search" element={<Navigate to="/" replace />} />
        <Route path="/persons" element={<Navigate to="/network" replace />} />
      </Routes>
    </Layout>
  )
}

export default App
