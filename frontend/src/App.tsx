import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Feed from './pages/Feed'
import SignalStory from './pages/SignalStory'
import Companies from './pages/Companies'
import CompanyDetail from './pages/CompanyDetail'
import NetworkPage from './pages/NetworkPage'
import Pricing from './pages/Pricing'
import Alerts from './pages/Alerts'
import Accuracy from './pages/Accuracy'
import TrackRecord from './pages/TrackRecord'
import Blog from './pages/Blog'
import CompanyIntelligence from './pages/CompanyIntelligence'

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
        <Route path="/company/:cik" element={<CompanyIntelligence />} />
        <Route path="/network" element={<NetworkPage />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/accuracy" element={<Accuracy />} />
        <Route path="/snapshot" element={<Navigate to="/track-record" replace />} />
        <Route path="/track-record" element={<TrackRecord />} />
        <Route path="/blog/insider-signal-research" element={<Blog />} />

        {/* Redirects for old routes */}
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
