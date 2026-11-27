import { NavLink } from 'react-router'

const links = [
  { to: '/network', label: 'Network' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/dispatch', label: 'Dispatch' },
  { to: '/approvals', label: 'Approvals' },
]

function Sidebar() {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
      <div className="border-b border-border px-6 py-5">
        <p className="text-lg font-semibold text-heading">HRC</p>
        <p className="text-xs text-heading/50">Resource Coordination</p>
      </div>

      <nav className="flex-1 p-4">
        <p className="px-4 pb-2 text-xs font-medium uppercase tracking-wide text-heading/50">
          Operations
        </p>
        <ul className="space-y-1">
          {links.map(link => (
            <li key={link.to}>
              <NavLink
                to={link.to}
                className={({ isActive }) =>
                  `block rounded-lg px-4 py-2.5 text-sm transition ${
                    isActive
                      ? 'bg-primary font-medium text-white shadow-sm'
                      : 'text-heading hover:bg-primary-soft'
                  }`
                }
              >
                {link.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="flex items-center gap-3 border-t border-border p-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-heading text-sm font-medium text-white">
          C
        </div>
        <div>
          <p className="text-sm font-medium text-heading">Coordinator</p>
          <p className="text-xs text-heading/50">On duty</p>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
