import { NavLink } from 'react-router-dom';

export default function Header() {
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
        <NavLink to="/history" className={({ isActive }) => `header__nav-link ${isActive ? 'header__nav-link--active' : ''}`}>
          History
        </NavLink>
      </nav>
    </header>
  );
}
