import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import SignalList from './pages/SignalList'
import SignalDetail from './pages/SignalDetail'
import PerformanceTracker from './pages/PerformanceTracker'
import Privacy from './pages/Privacy'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<SignalList />} />
        <Route path="/signal/:accessionNumber" element={<SignalDetail />} />
        <Route path="/performance" element={<PerformanceTracker />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

export default App
