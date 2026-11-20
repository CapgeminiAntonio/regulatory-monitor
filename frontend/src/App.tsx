import { NavLink, Route, Routes } from 'react-router-dom'
import { ScanButton } from './components/ScanButton'
import Feed from './pages/Feed'
import ItemDetail from './pages/ItemDetail'
import MatrixPage from './pages/Matrix'
import Policies from './pages/Policies'
import PolicyDetail from './pages/PolicyDetail'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium ${isActive ? 'bg-white/15 text-white' : 'text-blue-100 hover:text-white'}`

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="bg-blue-950 text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-6">
            <div>
              <div className="text-base font-semibold tracking-tight">Regulatory Change Monitor</div>
              <div className="text-xs text-blue-200">Client: Northwind Wealth & Asset Management (fictional)</div>
            </div>
            <nav className="flex gap-1">
              <NavLink to="/" end className={navClass}>Changes</NavLink>
              <NavLink to="/matrix" className={navClass}>Impact matrix</NavLink>
              <NavLink to="/policies" className={navClass}>Policies</NavLink>
            </nav>
          </div>
          <ScanButton />
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Feed />} />
          <Route path="/items/:id" element={<ItemDetail />} />
          <Route path="/matrix" element={<MatrixPage />} />
          <Route path="/policies" element={<Policies />} />
          <Route path="/policies/:id" element={<PolicyDetail />} />
        </Routes>
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-slate-400">
        AI-generated analysis using Claude. Verify against the source text before acting.
      </footer>
    </div>
  )
}
