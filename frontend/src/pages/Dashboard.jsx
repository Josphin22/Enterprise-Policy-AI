import React, { useState, useEffect } from 'react';
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
  XCircle
} from 'lucide-react';
import StatusCard from '../components/StatusCard';
import { getKnowledgeBaseStatus } from '../services/api';

export default function Dashboard({ healthState, onRefreshHealth, onNavigate }) {
  const { isConnected, isChecking, data, latencyMs, error } = healthState;
  const [kbStatus, setKbStatus] = useState({ documents: 0 });

  useEffect(() => {
    if (isConnected) {
      getKnowledgeBaseStatus().then((res) => {
        if (res.success && res.data) {
          setKbStatus(res.data);
        }
      });
    }
  }, [isConnected]);

  return (
    <div className="dashboard-page-container">
      {/* Welcome Banner */}
      <div className="page-header-intro">
        <div>
          <h1 className="page-main-heading">Executive Dashboard</h1>
          <p className="page-sub-heading">
            System overview and real-time infrastructure status for enterprise policy intelligence.
          </p>
        </div>
      </div>

      {/* Real-time Backend Infrastructure Health Card */}
      <section className="dashboard-hero-health-panel">
        <div className="health-panel-top">
          <div className="health-title-group">
            <Activity size={20} className="text-cyan" />
            <div>
              <h3>Core Backend API Infrastructure</h3>
              <p>Direct communication link with the FastAPI microservice</p>
            </div>
          </div>

          <button
            type="button"
            id="dashboard-refresh-health-btn"
            className={`btn-health-refresh ${isChecking ? 'spinning' : ''}`}
            onClick={onRefreshHealth}
            disabled={isChecking}
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
              {isConnected ? '✓ Backend Connected' : '✗ Backend Disconnected'}
            </div>
            {isConnected && data ? (
              <p className="health-status-details">
                Service: <strong>{data.service}</strong> &bull; API Health: <strong>{data.status}</strong> &bull; Round-Trip Latency: <strong>{latencyMs !== null ? `${latencyMs} ms` : '—'}</strong>
              </p>
            ) : (
              <p className="health-status-details error-text">
                {error || 'Unable to connect to FastAPI backend at http://localhost:8000. Please ensure the backend is running.'}
              </p>
            )}
          </div>
        </div>
      </section>

      {/* System Metrics Grid */}
      <section className="metrics-cards-grid">
        <StatusCard
          title="Total Documents"
          value={isConnected ? `${kbStatus.documents ?? 0} Uploaded` : "Not available"}
          subtitle="Indexed policy files in storage"
          icon={Files}
          badgeText={isConnected ? "Storage Active" : "Offline"}
          badgeType={isConnected ? "success" : "neutral"}
        />

        <StatusCard
          title="Processed Documents"
          value={isConnected ? `${kbStatus.processed_documents ?? 0} Processed` : "Not available"}
          subtitle="Text extracted and partitioned"
          icon={FileCheck}
          badgeText={isConnected && (kbStatus.processed_documents > 0) ? "Ready" : "Pending"}
          badgeType={isConnected && (kbStatus.processed_documents > 0) ? "success" : "neutral"}
        />

        <StatusCard
          title="Total Chunks"
          value={isConnected ? `${kbStatus.chunks ?? 0} Chunks` : "Not available"}
          subtitle="Partitioned text chunks in PostgreSQL"
          icon={Layers}
          badgeText={isConnected ? "Active" : "Offline"}
          badgeType={isConnected ? "success" : "neutral"}
        />

        <StatusCard
          title="Vector Database Status"
          value="Not built (0 vectors)"
          subtitle="FAISS similarity index engine"
          icon={Database}
          badgeText="Phase 6 Integration"
          badgeType="neutral"
        />

        <StatusCard
          title="AI Model Status"
          value="Not configured"
          subtitle="Ollama local LLM inference engine"
          icon={Cpu}
          badgeText="Phase 6 Integration"
          badgeType="neutral"
        />

        <StatusCard
          title="Backend Service Status"
          value={isConnected ? "Healthy & Active" : "Disconnected"}
          subtitle="FastAPI REST API Server"
          icon={Server}
          badgeText={isConnected ? "Online" : "Offline"}
          badgeType={isConnected ? "success" : "error"}
        />
      </section>

      {/* Quick Launchpad & RAG Pipeline Status */}
      <div className="dashboard-split-section">
        {/* Quick Launchpad Card */}
        <div className="enterprise-card">
          <div className="card-section-title">
            <ShieldCheck size={18} />
            <span>Quick Workspaces</span>
          </div>
          <p className="card-section-desc">
            Direct shortcuts to key enterprise policy assistant modules.
          </p>

          <div className="quick-actions-list">
            <button 
              type="button" 
              className="quick-action-item"
              onClick={() => onNavigate('documents')}
            >
              <div className="action-item-icon"><Files size={18} /></div>
              <div className="action-item-info">
                <strong>Manage Policy Documents</strong>
                <span>Upload PDF, DOCX, and TXT internal company guidelines</span>
              </div>
              <ArrowRight size={16} className="action-arrow" />
            </button>

            <button 
              type="button" 
              className="quick-action-item"
              onClick={() => onNavigate('assistant')}
            >
              <div className="action-item-icon"><Cpu size={18} /></div>
              <div className="action-item-info">
                <strong>Open AI Policy Assistant</strong>
                <span>Interactive grounded document question-answering console</span>
              </div>
              <ArrowRight size={16} className="action-arrow" />
            </button>

            <button 
              type="button" 
              className="quick-action-item"
              onClick={() => onNavigate('knowledge')}
            >
              <div className="action-item-icon"><Database size={18} /></div>
              <div className="action-item-info">
                <strong>Knowledge Base Overview</strong>
                <span>Inspect vector store configurations and chunk metrics</span>
              </div>
              <ArrowRight size={16} className="action-arrow" />
            </button>
          </div>
        </div>

        {/* Pipeline Readiness Roadmap Card */}
        <div className="enterprise-card">
          <div className="card-section-title">
            <Activity size={18} />
            <span>Implementation Phase Roadmap</span>
          </div>
          <p className="card-section-desc">
            Modular progression towards a fully localized RAG architecture.
          </p>

          <div className="roadmap-phase-list">
            <div className="roadmap-step completed">
              <span className="step-number">1</span>
              <div className="step-details">
                <strong>Phase 1: Project Setup & API Core</strong>
                <span>FastAPI backend, CORS, live health check endpoint</span>
              </div>
              <span className="step-status-tag tag-done">Completed</span>
            </div>

            <div className="roadmap-step completed">
              <span className="step-number">2</span>
              <div className="step-details">
                <strong>Phase 2: Professional Frontend UI</strong>
                <span>Enterprise dashboard, modular pages, responsive layout</span>
              </div>
              <span className="step-status-tag tag-done">Completed</span>
            </div>

            <div className="roadmap-step completed">
              <span className="step-number">3</span>
              <div className="step-details">
                <strong>Phase 3: FastAPI Backend & API Layer</strong>
                <span>Document storage, safe file handling, REST schemas & endpoints</span>
              </div>
              <span className="step-status-tag tag-done">Completed</span>
            </div>

            <div className="roadmap-step completed">
              <span className="step-number">4</span>
              <div className="step-details">
                <strong>Phase 4: PostgreSQL & SQLAlchemy Integration</strong>
                <span>Persistent relational tables, Alembic migrations, session storage</span>
              </div>
              <span className="step-status-tag tag-done">Completed</span>
            </div>

            <div className="roadmap-step completed">
              <span className="step-number">5</span>
              <div className="step-details">
                <strong>Phase 5: Text Extraction & Semantic Chunking</strong>
                <span>PDF/DOCX/TXT loaders, cleaning, recursive chunking, chunk inspector</span>
              </div>
              <span className="step-status-tag tag-done">Completed</span>
            </div>

            <div className="roadmap-step pending">
              <span className="step-number">6</span>
              <div className="step-details">
                <strong>Phase 6: SentenceTransformers Embeddings & FAISS Vector Index</strong>
                <span>Dense vector embedding, FAISS index build, similarity search</span>
              </div>
              <span className="step-status-tag tag-pending">Upcoming</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
