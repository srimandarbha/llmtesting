import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { createPortal } from 'react-dom'
import { Dashboard } from './pages/Dashboard'
import { IncidentDetail } from './pages/IncidentDetail'
import { Analytics } from './pages/Analytics'
import UpgradeAdvisor from './components/UpgradeAdvisor'

const NAV_ITEMS = [
  { to: '/',          label: 'Dashboard',  icon: '⚡', exact: true },
  { to: '/analytics', label: 'Analytics',  icon: '📊', exact: false },
  { to: '/upgrade-advisor', label: 'Advisor',  icon: '🛡️', exact: false },
]

function Sidebar({ appName, appSubtext, appLogo }: { appName: string, appSubtext: string, appLogo: string | null }) {
  return (
    <aside className="w-56 flex-shrink-0 flex flex-col bg-surface-800 border-r border-white/5 min-h-screen p-4">
      {/* Logo */}
      <div className="mb-8 px-1">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-violet-600
                          flex items-center justify-center text-base shadow-lg glow-brand no-invert overflow-hidden">
            {appLogo ? (
              <img src={appLogo} alt="App Logo" className="w-full h-full object-cover" />
            ) : (
              '🛡️'
            )}
          </div>
          <div className="overflow-hidden">
            <p className="text-sm font-bold text-white leading-tight truncate" title={appName}>{appName}</p>
            <p className="text-xs text-slate-500 leading-tight truncate" title={appSubtext}>{appSubtext}</p>
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
            <span className="no-invert">{item.icon}</span>
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

function SettingsModal({
  initialName, initialSubtext, initialLogo, onSave, onClose
}: {
  initialName: string, initialSubtext: string, initialLogo: string | null,
  onSave: (name: string, subtext: string, logo: string | null) => void,
  onClose: () => void
}) {
  const [name, setName] = useState(initialName)
  const [subtext, setSubtext] = useState(initialSubtext)
  const [logo, setLogo] = useState<string | null>(initialLogo)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onloadend = () => {
        setLogo(reader.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-surface-800 border border-white/10 rounded-xl p-6 w-96 shadow-2xl animate-fade-in" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-slate-200 mb-6">Branding Settings</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">App Name</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. SRE Agent" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">App Subtext</label>
            <input className="input" value={subtext} onChange={e => setSubtext(e.target.value)} placeholder="e.g. Incident Control" />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-500 mb-1">Logo Image</label>
            <input 
              type="file" 
              accept="image/*" 
              onChange={handleFileChange} 
              className="w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-brand-500/20 file:text-brand-400 hover:file:bg-brand-500/30 cursor-pointer" 
            />
            {logo && (
              <button className="mt-2 text-xs text-rose-400 hover:text-rose-300 transition-colors" onClick={() => setLogo(null)}>
                Remove Custom Logo
              </button>
            )}
          </div>
        </div>

        <div className="mt-8 flex justify-end gap-3">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={() => { onSave(name, subtext, logo); onClose(); }}>Save Changes</button>
        </div>
      </div>
    </div>,
    document.body
  )
}

function Layout({ children }: { children: React.ReactNode }) {
  const [isDay, setIsDay] = useState(false)
  const [appName, setAppName] = useState(() => localStorage.getItem('customAppName') || 'SRE Agent')
  const [appSubtext, setAppSubtext] = useState(() => localStorage.getItem('customAppSubtext') || 'Incident Control')
  const [appLogo, setAppLogo] = useState(() => localStorage.getItem('customAppLogo') || null)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)

  useEffect(() => {
    if (isDay) {
      document.documentElement.classList.remove('theme-night')
      document.documentElement.classList.add('theme-day')
    } else {
      document.documentElement.classList.remove('theme-day')
      document.documentElement.classList.add('theme-night')
    }
  }, [isDay])

  const handleSaveSettings = (n: string, s: string, l: string | null) => {
    setAppName(n)
    setAppSubtext(s)
    setAppLogo(l)
    localStorage.setItem('customAppName', n)
    localStorage.setItem('customAppSubtext', s)
    if (l) localStorage.setItem('customAppLogo', l)
    else localStorage.removeItem('customAppLogo')
  }

  return (
    <div className="flex min-h-screen relative">
      <Sidebar appName={appName} appSubtext={appSubtext} appLogo={appLogo} />
      
      {/* Sleek Action Bar */}
      <div className="absolute top-4 right-8 z-50 flex items-center gap-1.5 p-1 bg-surface-800/80 backdrop-blur-md border border-white/10 rounded-full shadow-lg">
        <button 
          onClick={() => setIsSettingsOpen(true)}
          className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-white/10 transition-colors text-slate-400 hover:text-white"
          title="Settings"
        >
          <span className="no-invert">⚙️</span>
        </button>
        <div className="w-px h-5 bg-white/10" />
        <button 
          onClick={() => setIsDay(!isDay)}
          className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-white/10 transition-colors text-slate-400 hover:text-white"
          title="Toggle Theme"
        >
          <span className="no-invert">{isDay ? '🌙' : '☀️'}</span>
        </button>
      </div>

      <main className="flex-1 overflow-auto p-8 pt-16">
        {children}
      </main>

      {isSettingsOpen && (
        <SettingsModal 
          initialName={appName}
          initialSubtext={appSubtext}
          initialLogo={appLogo}
          onSave={handleSaveSettings}
          onClose={() => setIsSettingsOpen(false)}
        />
      )}
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
          <Route path="/upgrade-advisor" element={<UpgradeAdvisor />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
