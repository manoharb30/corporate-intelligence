import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import SignalList from './pages/SignalList'
import SignalDetail from './pages/SignalDetail'
import PerformanceTracker from './pages/PerformanceTracker'
import Privacy from './pages/Privacy'
import McpDocs from './pages/McpDocs'
import Terms from './pages/Terms'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<SignalList />} />
        <Route path="/signal/:accessionNumber" element={<SignalDetail />} />
        <Route path="/performance" element={<PerformanceTracker />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/mcp" element={<McpDocs />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

export default App
