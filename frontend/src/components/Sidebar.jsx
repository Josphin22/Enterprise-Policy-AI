import React from 'react';
import { 
  LayoutDashboard, 
  Files, 
  Bot, 
  History, 
  Database, 
  BarChart3, 
  Settings, 
  ShieldCheck,
  X,
  Sparkles
} from 'lucide-react';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'documents', label: 'Documents', icon: Files },
  { id: 'assistant', label: 'AI Assistant', icon: Bot },
  { id: 'history', label: 'Chat History', icon: History },
  { id: 'knowledge', label: 'Knowledge Base', icon: Database },
  { id: 'evaluation', label: 'Evaluation', icon: BarChart3 },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export default function Sidebar({ 
  activePage, 
  onSelectPage, 
  isOpen = false, 
  onCloseMobile 
}) {
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

      <aside className={`app-sidebar ${isOpen ? 'open' : ''}`}>
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
                  >
                    <Icon size={19} className="nav-icon" />
                    <span className="nav-label">{item.label}</span>
                    {isActive && <span className="nav-active-pip" />}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Sidebar Footer Info */}
        <div className="sidebar-footer-card">
          <div className="footer-phase-tag">
            <Sparkles size={13} />
            <span>Phase 2: UI Foundation</span>
          </div>
          <p className="footer-copyright-text">
            Enterprise RAG Platform &bull; v0.2.0
          </p>
        </div>
      </aside>
    </>
  );
}
