import React, { useState, useEffect, useCallback } from 'react';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Documents from './pages/Documents';
import Assistant from './pages/Assistant';
import ChatHistory from './pages/ChatHistory';
import KnowledgeBase from './pages/KnowledgeBase';
import Evaluation from './pages/Evaluation';
import AdminDashboard from './pages/AdminDashboard';
import Settings from './pages/Settings';
import { getHealthStatus } from './services/api';

export default function App() {
  const [activePage, setActivePage] = useState('assistant');
  const [healthState, setHealthState] = useState({
    isConnected: false,
    isChecking: true,
    data: null,
    latencyMs: null,
    error: null,
  });

  const pollHealthStatus = useCallback(async () => {
    setHealthState((prev) => ({ ...prev, isChecking: true }));
    const result = await getHealthStatus();
    setHealthState({
      isConnected: result.isConnected,
      isChecking: false,
      data: result.data,
      latencyMs: result.latencyMs,
      error: result.error,
    });
  }, []);

  useEffect(() => {
    pollHealthStatus();
    // Poll every 30 seconds for background health status
    const interval = setInterval(pollHealthStatus, 30000);
    return () => clearInterval(interval);
  }, [pollHealthStatus]);

  const renderActivePage = () => {
    switch (activePage) {
      case 'dashboard':
        return (
          <Dashboard
            healthState={healthState}
            onRefreshHealth={pollHealthStatus}
            onNavigate={setActivePage}
          />
        );
      case 'documents':
        return <Documents />;
      case 'assistant':
        return <Assistant />;
      case 'history':
        return <ChatHistory />;
      case 'knowledge':
        return <KnowledgeBase />;
      case 'evaluation':
        return <Evaluation />;
      case 'admin':
        return <AdminDashboard onNavigate={setActivePage} />;
      case 'settings':
        return <Settings />;
      default:
        return (
          <Dashboard
            healthState={healthState}
            onRefreshHealth={pollHealthStatus}
            onNavigate={setActivePage}
          />
        );
    }
  };

  return (
    <Layout
      activePage={activePage}
      onSelectPage={setActivePage}
      healthState={healthState}
      onRefreshHealth={pollHealthStatus}
    >
      {renderActivePage()}
    </Layout>
  );
}
