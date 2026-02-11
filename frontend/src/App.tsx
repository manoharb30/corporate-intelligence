import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Feed from './pages/Feed'
import CompanyProfile from './pages/CompanyProfile'
import Intelligence from './pages/Intelligence'
import Dashboard from './pages/Dashboard'
import Companies from './pages/Companies'
import CompanyDetail from './pages/CompanyDetail'
import Persons from './pages/Persons'
import GraphExplorer from './pages/GraphExplorer'
import Search from './pages/Search'
import ConnectionsPage from './pages/ConnectionsPage'
import EventDetail from './pages/EventDetail'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Feed />} />
        <Route path="/company/:cik" element={<CompanyProfile />} />
        <Route path="/event/:accessionNumber" element={<EventDetail />} />
        <Route path="/intelligence" element={<Intelligence />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/companies" element={<Companies />} />
        <Route path="/companies/:id" element={<CompanyDetail />} />
        <Route path="/persons" element={<Persons />} />
        <Route path="/graph" element={<GraphExplorer />} />
        <Route path="/search" element={<Search />} />
        <Route path="/connections" element={<ConnectionsPage />} />
      </Routes>
    </Layout>
  )
}

export default App
