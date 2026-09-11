import React, { useState, useEffect } from 'react';
import { ShieldCheck, Menu, User, RefreshCw, Palette, Sun, Moon, Sparkles, Check } from 'lucide-react';

const THEMES = [
  { id: 'dark', label: 'ChatGPT Dark', icon: Moon },
  { id: 'light', label: 'Modern Light', icon: Sun },
  { id: 'midnight', label: 'Midnight Blue', icon: Sparkles },
  { id: 'emerald', label: 'Emerald Mint', icon: Palette },
];

export default function Header({ 
  isConnected = false, 
  isChecking = false,
  onRefreshHealth,
  onToggleSidebar,
  currentPageTitle = 'Dashboard'
}) {
  const [currentTheme, setCurrentTheme] = useState(() => {
    return localStorage.getItem('app_theme') || 'dark';
  });
  const [showThemeMenu, setShowThemeMenu] = useState(false);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('app_theme', currentTheme);
  }, [currentTheme]);

  const selectTheme = (themeId) => {
    setCurrentTheme(themeId);
    setShowThemeMenu(false);
  };
  return (
    <header className="app-top-header">
      <div className="header-left">
        <button
          type="button"
          className="btn-sidebar-toggle"
          onClick={onToggleSidebar}
          aria-label="Toggle navigation menu"
        >
          <Menu size={20} />
        </button>

        <div className="header-breadcrumbs">
          <span className="breadcrumb-root">Enterprise Policy AI</span>
          <span className="breadcrumb-separator">/</span>
          <span className="breadcrumb-current">{currentPageTitle}</span>
        </div>
      </div>

      <div className="header-right" style={{ position: 'relative' }}>
        {/* Theme Picker Dropdown */}
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            className="system-status-pill"
            style={{ cursor: 'pointer', background: 'rgba(255, 255, 255, 0.08)', border: '1px solid rgba(255, 255, 255, 0.15)', display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.35rem 0.75rem', borderRadius: '8px' }}
            onClick={() => setShowThemeMenu((prev) => !prev)}
            title="Change Theme"
          >
            <Palette size={14} className="text-cyan" />
            <span style={{ fontSize: '0.8rem', color: 'var(--text-primary)', fontWeight: 500 }}>
              Theme: {THEMES.find(t => t.id === currentTheme)?.label}
            </span>
          </button>

          {showThemeMenu && (
            <div
              style={{
                position: 'absolute',
                right: 0,
                top: 'calc(100% + 8px)',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-card)',
                borderRadius: '10px',
                padding: '0.5rem',
                minWidth: '180px',
                boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
                zIndex: 100,
                display: 'flex',
                flexDirection: 'column',
                gap: '0.25rem',
              }}
            >
              {THEMES.map((theme) => {
                const Icon = theme.icon;
                const isSelected = currentTheme === theme.id;
                return (
                  <button
                    key={theme.id}
                    type="button"
                    onClick={() => selectTheme(theme.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      width: '100%',
                      padding: '0.5rem 0.75rem',
                      borderRadius: '6px',
                      background: isSelected ? 'var(--bg-hover)' : 'transparent',
                      border: 'none',
                      color: isSelected ? 'var(--accent-cyan)' : 'var(--text-primary)',
                      cursor: 'pointer',
                      fontSize: '0.85rem',
                      fontWeight: isSelected ? 600 : 400,
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Icon size={14} />
                      <span>{theme.label}</span>
                    </div>
                    {isSelected && <Check size={14} />}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Real-time System Status Indicator */}
        <div 
          className={`system-status-pill ${isConnected ? 'online' : 'offline'}`}
          title={isConnected ? "FastAPI Backend is reachable" : "FastAPI Backend is disconnected"}
        >
          <span className={`status-dot ${isChecking ? 'checking' : isConnected ? 'online' : 'offline'}`}></span>
          <span className="status-text">
            {isChecking ? 'Checking...' : isConnected ? 'System Online' : 'System Offline'}
          </span>
          {onRefreshHealth && (
            <button
              type="button"
              className={`btn-header-refresh ${isChecking ? 'spin-animation' : ''}`}
              onClick={onRefreshHealth}
              title="Refresh connection status"
              aria-label="Refresh connection status"
            >
              <RefreshCw size={12} />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
