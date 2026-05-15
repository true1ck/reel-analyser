import { NavLink } from 'react-router-dom';

export default function Sidebar({ theme, toggleTheme }) {
  return (
    <aside className="sidebar">
      <div className="sidebar__logo">
        <span className="sidebar__logo-icon">🎬</span>
        <span className="gradient-text">Reel Analyser</span>
      </div>
      <nav className="sidebar__nav">
        <div className="sidebar__nav-group">
          <NavLink to="/" className={({ isActive }) => `sidebar__nav-link ${isActive ? 'sidebar__nav-link--active' : ''}`} end>
            <span className="sidebar__nav-icon">📊</span> Dashboard
          </NavLink>
          <NavLink to="/history" className={({ isActive }) => `sidebar__nav-link ${isActive ? 'sidebar__nav-link--active' : ''}`}>
            <span className="sidebar__nav-icon">🕒</span> History
          </NavLink>
          <NavLink to="/collections" className={({ isActive }) => `sidebar__nav-link ${isActive ? 'sidebar__nav-link--active' : ''}`}>
            <span className="sidebar__nav-icon">📁</span> Collections
          </NavLink>
          <NavLink to="/hub" className={({ isActive }) => `sidebar__nav-link ${isActive ? 'sidebar__nav-link--active' : ''}`}>
            <span className="sidebar__nav-icon">📈</span> Analytics
          </NavLink>
        </div>
        
        <div className="sidebar__nav-bottom">
          <button 
            className="sidebar__nav-link sidebar__theme-toggle"
            onClick={toggleTheme} 
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            <span className="sidebar__nav-icon">{theme === 'dark' ? '☀️' : '🌙'}</span> {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
          </button>
        </div>
      </nav>
    </aside>
  );
}
