import React from 'react';
import { ShieldCheck, Menu, User, RefreshCw } from 'lucide-react';

export default function Header({ 
  isConnected = false, 
  isChecking = false,
  onRefreshHealth,
  onToggleSidebar,
  currentPageTitle = 'Dashboard'
}) {
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

      <div className="header-right">
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

        {/* User Profile Placeholder */}
        <div className="user-profile-widget" tabIndex={0} role="button" aria-label="User Profile">
          <div className="user-avatar-circle">
            <User size={16} />
          </div>
          <div className="user-meta-compact">
            <span className="user-name-text">Enterprise Admin</span>
            <span className="user-role-text">Policy Specialist</span>
          </div>
        </div>
      </div>
    </header>
  );
}
