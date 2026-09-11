import React, { useState, useEffect } from 'react';
import { 
  LayoutDashboard, 
  Files, 
  Bot, 
  History, 
  Database, 
  BarChart3, 
  Settings, 
  ShieldCheck,
  Shield,
  Lock,
  X,
  Sparkles,
  User
} from 'lucide-react';
import { getStoredUser } from '../services/api';

const NAV_ITEMS = [
  { id: 'assistant', label: 'AI Assistant', icon: Bot },
  { id: 'documents', label: 'Documents', icon: Files },
  { id: 'history', label: 'Chat History', icon: History },
];

export default function Sidebar({ 
  activePage, 
  onSelectPage, 
  isOpen = false, 
  onCloseMobile 
}) {
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    setCurrentUser(getStoredUser());
  }, [activePage]);

  const isAdmin = currentUser?.role === 'ADMIN';

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isOpen && (
        <div 
          className="sidebar-backdrop" 
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      <aside className={`app-sidebar ${isOpen ? 'open' : ''}`} aria-label="Enterprise Navigation">
        {/* Sidebar Header / Branding */}
        <div className="sidebar-brand-box">
          <div className="sidebar-brand-content">
            <div className="brand-logo-icon">
              <ShieldCheck size={22} />
            </div>
            <div className="brand-text-block">
              <h2 className="brand-title">Enterprise Policy</h2>
              <span className="brand-tag">AI Assistant</span>
            </div>
          </div>

          <button 
            type="button" 
            className="btn-sidebar-close" 
            onClick={onCloseMobile}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <div className="sidebar-subtitle-label">
          Local Retrieval-Augmented Generation System
        </div>

        {/* Navigation Links */}
        <nav className="sidebar-nav" aria-label="Main Navigation">
          <ul className="nav-list">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = activePage === item.id;
              
              return (
                <li key={item.id} className="nav-item">
                  <button
                    type="button"
                    className={`nav-link-btn ${isActive ? 'active' : ''}`}
                    onClick={() => {
                      onSelectPage(item.id);
                      if (onCloseMobile) onCloseMobile();
                    }}
                    aria-current={isActive ? 'page' : undefined}
                    aria-label={`Navigate to ${item.label}`}
                  >
                    <Icon size={19} className="nav-icon" />
                    <span className="nav-label">{item.label}</span>
                    {item.adminOnly && (
                      <span 
                        className={`sidebar-role-tag ${isAdmin ? 'role-admin' : 'role-locked'}`} 
                        title={isAdmin ? "Full Admin Access" : "Admin Authentication Required"}
                      >
                        {isAdmin ? 'ADMIN' : 'RBAC'}
                      </span>
                    )}
                    {isActive && <span className="nav-active-pip" />}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Sidebar Footer User / Phase Tag */}
        <div className="sidebar-footer-card">
          <div className="sidebar-user-pill">
            <User size={13} className="text-cyan" />
            <span className="sidebar-user-name">
              {currentUser ? currentUser.email : 'Policy User'}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}
