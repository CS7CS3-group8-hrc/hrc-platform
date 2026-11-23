import { useLocation } from 'react-router'

const titles: Record<string, string> = {
  '/network': 'Network Capacity',
  '/alerts': 'Bottleneck Alerts',
  '/dispatch': 'Dispatch Console',
  '/approvals': 'Pending Approvals',
}

function TopBar() {
  const { pathname } = useLocation()

  return (
    <header className="flex items-center justify-between border-b border-border bg-surface px-8 py-5">
      <div>
        <h1 className="text-xl font-semibold text-heading">
          {titles[pathname] ?? 'HealthLoop'}
        </h1>
        <p className="text-sm text-heading/50">Live hospital overview</p>
      </div>

      <div className="flex items-center gap-3">
        <span className="rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-primary">
          ● Live
        </span>
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-heading text-sm font-medium text-white">
          C
        </div>
      </div>
    </header>
  )
}

export default TopBar
