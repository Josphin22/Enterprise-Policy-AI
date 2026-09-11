import React, { useState, useEffect, useCallback } from 'react';
import { 
  Server, 
  Files, 
  FileCheck, 
  Layers, 
  Database, 
  Cpu, 
  RefreshCw, 
  ArrowRight, 
  ShieldCheck, 
  Activity,
  CheckCircle2,
  XCircle,
  MessageSquare,
  Clock,
  ChevronRight
} from 'lucide-react';
import StatusCard from '../components/StatusCard';
import { 
  getKnowledgeBaseStatus, 
  getOllamaHealth, 
  getConversations
} from '../services/api';

export default function Dashboard({ healthState, onRefreshHealth, onNavigate }) {
  const { isConnected, isChecking, data, latencyMs, error } = healthState;
  
  const [kbStatus, setKbStatus] = useState({
    documents: 0,
    processed_documents: 0,
    chunks: 0,
    vectors: 0,
    status: 'not_built',
    last_built: null,
    vector_database: 'FAISS',
    embedding_model: 'sentence-transformers/all-MiniLM-L6-v2',
    embedding_dimension: 384
  });

  const [ollamaInfo, setOllamaInfo] = useState({
    available: false,
    model: 'llama3.2:3b'
  });

  const [recentConversations, setRecentConversations] = useState([]);
  const [isLoadingDashboard, setIsLoadingDashboard] = useState(false);

  const fetchLiveDashboardData = useCallback(async () => {
    if (!isConnected) return;
    setIsLoadingDashboard(true);
    try {
      const [kbRes, ollamaRes, convRes] = await Promise.all([
        getKnowledgeBaseStatus(),
        getOllamaHealth(),
        getConversations()
      ]);

      if (kbRes.success && kbRes.data) {
        setKbStatus(kbRes.data);
      }
      if (ollamaRes.success && ollamaRes.data) {
        setOllamaInfo({
          available: ollamaRes.data.available,
          model: ollamaRes.data.model || 'llama3.2:3b'
        });
      }
      if (convRes.success && convRes.sessions) {
        setRecentConversations(convRes.sessions.slice(0, 5));
      }
    } catch (err) {
      console.warn('Error updating dashboard metrics:', err);
    } finally {
      setIsLoadingDashboard(false);
    }
  }, [isConnected]);

  useEffect(() => {
    fetchLiveDashboardData();
  }, [fetchLiveDashboardData]);

  const isKbReady = (kbStatus.status === 'ready' || kbStatus.status === 'active') && kbStatus.vectors > 0;

  return (
    <div className="dashboard-page-container">
      {/* Welcome Banner */}
      <div className="page-header-intro">
        <div>
          <h1 className="page-main-heading">Executive Dashboard</h1>
          <p className="page-sub-heading">
            Live operational intelligence and empirical metrics across your enterprise policy assistant.
          </p>
        </div>
        <div className="header-action-group">
          <button
            type="button"
            className={`btn-action-ghost ${isChecking || isLoadingDashboard ? 'spinning' : ''}`}
            onClick={() => {
              onRefreshHealth();
              fetchLiveDashboardData();
            }}
            disabled={isChecking || isLoadingDashboard}
            aria-label="Refresh dashboard metrics"
          >
            <RefreshCw size={15} />
            <span>{isChecking || isLoadingDashboard ? 'Refreshing...' : 'Refresh Metrics'}</span>
          </button>
        </div>
      </div>

      {/* Real-time Backend Infrastructure Health Card */}
      <section className="dashboard-hero-health-panel" aria-label="Backend Health Status">
        <div className="health-panel-top">
          <div className="health-title-group">
            <Activity size={20} className="text-cyan" />
            <div>
              <h3>Core Microservice Infrastructure</h3>
              <p>Direct communication link with the FastAPI application and PostgreSQL persistence engine</p>
            </div>
          </div>

          <button
            type="button"
            id="dashboard-refresh-health-btn"
            className={`btn-health-refresh ${isChecking ? 'spinning' : ''}`}
            onClick={onRefreshHealth}
            disabled={isChecking}
            aria-label="Check backend connection"
          >
            <RefreshCw size={14} />
            <span>{isChecking ? 'Checking Link...' : 'Check Connection'}</span>
          </button>
        </div>

        {/* Dynamic Health Badge */}
        <div className={`health-status-display-banner ${isConnected ? 'status-connected' : 'status-disconnected'}`}>
          <div className="health-badge-icon">
            {isConnected ? <CheckCircle2 size={28} /> : <XCircle size={28} />}
          </div>
          <div className="health-badge-info">
            <div className="health-status-primary-text">
              {isConnected ? '✓ Backend Microservice Connected' : '✗ Backend Microservice Disconnected'}
            </div>
            {isConnected && data ? (
              <p className="health-status-details">
                Service: <strong>{data.service || 'enterprise-rag-api'}</strong> &bull; Status: <strong>{data.status}</strong> &bull; Round-Trip Latency: <strong>{latencyMs !== null ? `${latencyMs} ms` : '—'}</strong> &bull; Mode: <strong>Production Local RAG</strong>
              </p>
            ) : (
              <p className="health-status-details error-text">
                {error || 'Unable to connect to FastAPI backend at http://localhost:8000. Please verify the Python service is active.'}
              </p>
            )}
          </div>
        </div>
      </section>

      {/* System Metrics Grid with 100% Real Empirical Backend Data */}
      <section className="metrics-cards-grid" aria-label="System Metrics Summary">
        <StatusCard
          title="Total Documents"
          value={isConnected ? `${kbStatus.documents ?? 0} Uploaded` : "Not available"}
          subtitle="Managed policy files in repository"
          icon={Files}
          badgeText={isConnected ? "Storage Active" : "Offline"}
          badgeType={isConnected ? "success" : "neutral"}
        />

        <StatusCard
          title="Processed Documents"
          value={isConnected ? `${kbStatus.processed_documents ?? 0} Processed` : "Not available"}
          subtitle="Extracted, normalized & partitioned"
          icon={FileCheck}
          badgeText={isConnected && (kbStatus.processed_documents > 0) ? "Ready" : "Pending Processing"}
          badgeType={isConnected && (kbStatus.processed_documents > 0) ? "success" : "neutral"}
        />

        <StatusCard
          title="Semantic Chunks"
          value={isConnected ? `${kbStatus.chunks ?? 0} Chunks` : "Not available"}
          subtitle="Relational text chunks in PostgreSQL"
          icon={Layers}
          badgeText={isConnected && kbStatus.chunks > 0 ? "Partitioned" : "Empty"}
          badgeType={isConnected && kbStatus.chunks > 0 ? "success" : "neutral"}
        />

        <StatusCard
          title="FAISS Vector Index"
          value={isConnected ? (isKbReady ? `${kbStatus.vectors} Vectors` : "0 (Not Built)") : "Not available"}
          subtitle={isKbReady ? `${kbStatus.embedding_dimension || 384}-dim dense cosine index` : "Rebuild required to index chunks"}
          icon={Database}
          badgeText={isKbReady ? "Online & Searchable" : "Build Required"}
          badgeType={isKbReady ? "success" : "warning"}
        />

        <StatusCard
          title="Local LLM Inference"
          value={isConnected ? (ollamaInfo.available ? ollamaInfo.model : "Daemon Offline") : "Not available"}
          subtitle="Ollama localized RAG generation"
          icon={Cpu}
          badgeText={ollamaInfo.available ? "Ollama Active" : "Local Fallback"}
          badgeType={ollamaInfo.available ? "success" : "warning"}
        />

        <StatusCard
          title="FastAPI Core Engine"
          value={isConnected ? "Healthy & Serving" : "Disconnected"}
          subtitle="REST API & RAG pipeline server"
          icon={Server}
          badgeText={isConnected ? "Online" : "Offline"}
          badgeType={isConnected ? "success" : "error"}
        />
      </section>

      {/* Quick Launchpad & Live Recent Policy Conversations */}
      <div className="dashboard-split-section">
        {/* Quick Workspaces Navigation Card */}
        <div className="enterprise-card">
          <div className="card-section-title">
            <ShieldCheck size={18} className="text-cyan" />
            <span>Operational Workspaces</span>
          </div>
          <p className="card-section-desc">
            Direct shortcuts to key enterprise policy assistant modules.
          </p>

          <div className="quick-actions-list">
            <button 
              type="button" 
              className="quick-action-item"
              onClick={() => onNavigate('documents')}
              aria-label="Navigate to policy documents"
            >
              <div className="action-item-icon"><Files size={18} /></div>
              <div className="action-item-info">
                <strong>Policy Documents Repository</strong>
                <span>Upload PDF, DOCX, and TXT internal company guidelines & inspect chunks</span>
              </div>
              <ArrowRight size={16} className="action-arrow" />
            </button>

            <button 
              type="button" 
              className="quick-action-item"
              onClick={() => onNavigate('assistant')}
              aria-label="Navigate to AI Assistant"
            >
              <div className="action-item-icon"><Cpu size={18} /></div>
              <div className="action-item-info">
                <strong>AI Policy Assistant</strong>
                <span>Interactive multi-turn grounded document question-answering console</span>
              </div>
              <ArrowRight size={16} className="action-arrow" />
            </button>

            <button 
              type="button" 
              className="quick-action-item"
              onClick={() => onNavigate('knowledge')}
              aria-label="Navigate to Knowledge Base"
            >
              <div className="action-item-icon"><Database size={18} /></div>
              <div className="action-item-info">
                <strong>Knowledge Base Management</strong>
                <span>Inspect vector counts, trigger FAISS rebuilds & verify semantic retrieval</span>
              </div>
              <ArrowRight size={16} className="action-arrow" />
            </button>

            <button 
              type="button" 
              className="quick-action-item"
              onClick={() => onNavigate('admin')}
              aria-label="Navigate to Enterprise Admin Portal"
            >
              <div className="action-item-icon"><Activity size={18} /></div>
              <div className="action-item-info">
                <strong>Enterprise Admin Portal</strong>
                <span>User RBAC, system audit logs, system health diagnostics & analytics</span>
              </div>
              <ArrowRight size={16} className="action-arrow" />
            </button>
          </div>
        </div>

        {/* Real Live Recent Conversations / Activity */}
        <div className="enterprise-card">
          <div className="card-section-title">
            <MessageSquare size={18} className="text-indigo" />
            <span>Recent Policy Inquiries</span>
          </div>
          <p className="card-section-desc">
            Empirical inquiry threads recorded in the persistent database.
          </p>

          <div className="recent-conversations-list">
            {recentConversations.length === 0 ? (
              <div className="dashboard-empty-threads">
                <Clock size={28} className="text-muted" style={{ margin: '0 auto 0.5rem auto' }} />
                <p>Start a conversation with your policy assistant.</p>
                <button
                  type="button"
                  className="btn-action-primary"
                  style={{ marginTop: '0.75rem' }}
                  onClick={() => onNavigate('assistant')}
                >
                  Ask Policy Question
                </button>
              </div>
            ) : (
              recentConversations.map((conv) => {
                const convId = conv.id || conv.session_id;
                const formattedDate = conv.created_at 
                  ? new Date(conv.created_at).toLocaleDateString() + ' ' + new Date(conv.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : 'Recent session';
                
                return (
                  <button
                    key={convId}
                    type="button"
                    className="recent-conv-item"
                    onClick={() => onNavigate('assistant')}
                    title={`Open thread: ${conv.title || 'Policy Discussion'}`}
                  >
                    <div className="conv-item-icon">
                      <MessageSquare size={14} className="text-cyan" />
                    </div>
                    <div className="conv-item-content">
                      <strong className="conv-item-title">{conv.title || 'Policy Inquiry'}</strong>
                      <span className="conv-item-date">{formattedDate}</span>
                    </div>
                    <ChevronRight size={14} className="conv-item-arrow" />
                  </button>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


