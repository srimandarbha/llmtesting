import React from 'react'
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { IncidentDetail } from './pages/IncidentDetail'
import { Analytics } from './pages/Analytics'

const NAV_ITEMS = [
  { to: '/',          label: 'Dashboard',  icon: '⚡', exact: true },
  { to: '/analytics', label: 'Analytics',  icon: '📊', exact: false },
]

function Sidebar() {
  return (
    <aside className="w-56 flex-shrink-0 flex flex-col bg-surface-800 border-r border-white/5 min-h-screen p-4">
      {/* Logo */}
      <div className="mb-8 px-1">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-violet-600
                          flex items-center justify-center text-base shadow-lg glow-brand">
            🛡️
          </div>
          <div>
            <p className="text-sm font-bold text-white leading-tight">SRE Agent</p>
            <p className="text-xs text-slate-500 leading-tight">Incident Control</p>
          </div>
        </div>
      </div>

      {/* Nav links */}
      <nav className="flex-1 space-y-1">
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.exact}
            className={({ isActive }) =>
              `nav-link ${isActive ? 'active' : ''}`
            }
          >
            <span>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="mt-auto pt-4 border-t border-white/5">
        <p className="text-xs text-slate-600 text-center">LangChain v2 · FastAPI</p>
      </div>
    </aside>
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto p-8">
        {children}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/incidents/:id" element={<IncidentDetail />} />
          <Route path="/analytics" element={<Analytics />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
