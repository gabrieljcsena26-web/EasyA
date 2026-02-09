import React from 'react'
import { NavLink } from 'react-router-dom'

const Sidebar = ({ collapsed }) => {
  return (
    <aside className={`dashboard-sidebar ${collapsed ? 'collapsed' : ''}`} data-e2e="sidebar">
      <nav>
        <ul>
          <li data-e2e="nav-dashboard">
            <NavLink to="/dashboard" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>Dashboard</NavLink>
          </li>
          <li data-e2e="nav-admin-config">
            <NavLink to="/config" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>Configurações</NavLink>
          </li>
          <li data-e2e="nav-clients">
            <NavLink to="/clientes" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>Clientes</NavLink>
          </li>
          <li data-e2e="nav-finance">
            <NavLink to="/financas" className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>Finanças</NavLink>
          </li>
        </ul>
      </nav>
    </aside>
  )
}

export default Sidebar
