import { NavLink } from 'react-router-dom';

export default function Header({ theme, toggleTheme }) {
  return (
    <header className="header">
      <div className="header__logo">
        <span className="header__logo-icon">🎬</span>
        <span className="gradient-text">Reel Analyser</span>
      </div>
      <nav className="header__nav">
        <NavLink to="/" className={({ isActive }) => `header__nav-link ${isActive ? 'header__nav-link--active' : ''}`} end>
          Dashboard
        </NavLink>
        <NavLink to="/collections" className={({ isActive }) => `header__nav-link ${isActive ? 'header__nav-link--active' : ''}`}>
          Collections
        </NavLink>
        <NavLink to="/history" className={({ isActive }) => `header__nav-link ${isActive ? 'header__nav-link--active' : ''}`}>
          History
        </NavLink>
        <NavLink to="/hub" className={({ isActive }) => `header__nav-link ${isActive ? 'header__nav-link--active' : ''}`}>
          Hub
        </NavLink>
        <button 
          onClick={toggleTheme} 
          style={{
            background: 'var(--bg-surface)', border: '1px solid var(--border-color)',
            color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)',
            width: '36px', height: '36px', display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', marginLeft: '16px', transition: 'var(--transition)'
          }}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--border-hover)'}
          onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border-color)'}
        >
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
      </nav>
    </header>
  );
}
