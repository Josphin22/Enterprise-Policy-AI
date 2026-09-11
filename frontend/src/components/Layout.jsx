import React, { useState } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

const PAGE_TITLES = {
  dashboard: 'Executive Dashboard',
  documents: 'Document Ingestion & Management',
  assistant: 'AI Policy Assistant',
  history: 'Conversation History',
  knowledge: 'Vector Knowledge Base',
  evaluation: 'Model Evaluation & Quality Benchmarks',
  admin: 'Enterprise Admin Portal',
  settings: 'System & Engine Settings',
};

export default function Layout({
  activePage,
  onSelectPage,
  healthState,
  onRefreshHealth,
  children,
}) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const toggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  const closeSidebar = () => {
    setIsSidebarOpen(false);
  };

  return (
    <div className="app-layout-shell">
      {/* Sidebar Navigation */}
      <Sidebar
        activePage={activePage}
        onSelectPage={onSelectPage}
        isOpen={isSidebarOpen}
        onCloseMobile={closeSidebar}
      />

      {/* Main Viewport Container */}
      <div className="app-main-viewport">
        <Header
          isConnected={healthState.isConnected}
          isChecking={healthState.isChecking}
          onRefreshHealth={onRefreshHealth}
          onToggleSidebar={toggleSidebar}
          currentPageTitle={PAGE_TITLES[activePage] || 'Dashboard'}
        />

        {/* Page Content Outlet */}
        <main className="app-page-outlet" id="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}
