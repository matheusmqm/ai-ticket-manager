import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Criar from './pages/Criar.jsx'
import Acompanhar from './pages/Acompanhar.jsx'
import Metricas from './pages/Metricas.jsx'
import { Logo } from './ui.jsx'

export default function App() {
  return (
    <>
      <header className="topo">
        <div className="topo-in">
          <div className="marca">
            <Logo />
            <span>Central de Chamados</span>
          </div>
          <nav aria-label="Principal">
            <NavLink to="/criar">Novo chamado</NavLink>
            <NavLink to="/acompanhar">Acompanhamento</NavLink>
            <NavLink to="/metricas">Métricas</NavLink>
          </nav>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/criar" replace />} />
          <Route path="/criar" element={<Criar />} />
          <Route path="/acompanhar" element={<Acompanhar />} />
          <Route path="/metricas" element={<Metricas />} />
        </Routes>
      </main>
    </>
  )
}
