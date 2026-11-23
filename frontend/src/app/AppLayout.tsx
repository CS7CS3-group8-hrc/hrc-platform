import { Outlet } from 'react-router'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

function AppLayout() {
  return (
    <div className="flex min-h-screen bg-page">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppLayout
