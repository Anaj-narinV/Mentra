import { NavLink, Outlet } from "react-router-dom"
import { useAuth } from "../state/AuthContext.jsx"

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: "\u25a4" },
  { to: "/roadmap", label: "Roadmap", icon: "\u2246" },
  { to: "/tasks", label: "Tasks", icon: "\u2713" },
  { to: "/chat", label: "Chat", icon: "\u2699" },
  { to: "/notifications", label: "Notifications", icon: "\u2022" },
]

export default function AppShell() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-bg md:flex">
      {/* Desktop sidebar */}
      <aside className="hidden w-56 shrink-0 border-r border-line bg-surface md:flex md:flex-col">
        <div className="px-5 py-6">
          <span className="font-serif text-xl text-primary">Mentra</span>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium ${
                  isActive ? "bg-primary/10 text-primary" : "text-ink hover:bg-primary/5"
                }`
              }
            >
              <span aria-hidden>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-line px-5 py-4">
          <p className="text-sm text-muted">{user?.name}</p>
          <button onClick={logout} className="mt-1 text-sm font-medium text-primary">
            Log out
          </button>
        </div>
      </aside>

      <div className="flex-1 pb-16 md:pb-0">
        <main className="mx-auto w-full max-w-content px-4 py-6 md:px-8 md:py-10">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom tab bar */}
      <nav className="fixed inset-x-0 bottom-0 z-10 flex border-t border-line bg-surface md:hidden">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center gap-0.5 py-2.5 text-xs ${isActive ? "text-primary" : "text-muted"}`
            }
          >
            <span aria-hidden className="text-base">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
