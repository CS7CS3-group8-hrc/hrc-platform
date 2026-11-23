import { Navigate, Route, Routes } from 'react-router'
import AppLayout from './app/AppLayout'
import NetworkPage from './features/NetworkPage'
import AlertsPage from './features/AlertsPage'
import DispatchPage from './features/DispatchPage'
import ApprovalPage from './features/ApprovalPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/network" replace />} />
      <Route element={<AppLayout />}>
        <Route path="/network" element={<NetworkPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/dispatch" element={<DispatchPage />} />
        <Route path="/approvals" element={<ApprovalPage />} />
      </Route>
    </Routes>
  )
}

export default App
