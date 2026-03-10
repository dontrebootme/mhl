import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Games from './pages/Games.jsx'
import Standings from './pages/Standings.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Dashboard />} />
          <Route path="games" element={<Games />} />
          <Route path="standings" element={<Standings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
