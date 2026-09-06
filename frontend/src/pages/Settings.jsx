import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Cpu, Database, Server, Info, Shield, HardDrive, CheckCircle2, RefreshCw } from 'lucide-react';
import { getLLMStatus, getLLMModels, getSystemStatus } from '../services/api';

export default function Settings() {
  const [llmStatus, setLlmStatus] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const [statRes, modelRes] = await Promise.all([getLLMStatus(), getLLMModels()]);
      if (statRes.success) setLlmStatus(statRes.data);
      if (modelRes.success) setAvailableModels(modelRes.models);
    } catch (e) {
      console.warn("Settings fetch error:", e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="settings-page-container">
      {/* Page Header */}
      <div className="page-header-intro">
        <div className="header-text-block">
          <h1 className="page-main-heading">System & Engine Settings</h1>
          <p className="page-sub-heading">
            Configuration parameters for local Ollama LLM inference, embedding models, vector stores, and application privacy.
          </p>
        </div>

        <button
          type="button"
          className="btn-action-primary"
          onClick={fetchStatus}
          disabled={loading}
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          <span>Probe Engine</span>
        </button>
      </div>

      <div className="settings-sections-grid">
        {/* Section 1: AI Model Settings */}
        <div className="enterprise-card settings-card">
          <div className="card-section-title">
            <Cpu size={18} className="text-cyan" />
            <span>Local LLM & Inference Engine (Phase 8)</span>
          </div>
          <p className="card-section-desc">
            On-premise foundation model and semantic embedding engine definitions.
          </p>

          <div className="settings-form-grid">
            <div className="form-group">
              <label htmlFor="llm-provider">LLM Provider</label>
              <input
                id="llm-provider"
                type="text"
                className="form-control"
                value="Ollama (Local On-Premise Daemon)"
                disabled
              />
              <span className="form-hint">Foundation model engine runs locally at http://127.0.0.1:11434</span>
            </div>

            <div className="form-group">
              <label htmlFor="llm-model">Configured Local Model</label>
              <input
                id="llm-model"
                type="text"
                className="form-control"
                value={llmStatus?.model || 'llama3.2:3b'}
                disabled
              />
              <span className="form-hint">
                Status: {llmStatus?.status === 'available' ? '🟢 Online & Ready' : '🟡 Model check / daemon offline'}
              </span>
            </div>

            <div className="form-group">
              <label htmlFor="embedding-model">Embedding Model</label>
              <input
                id="embedding-model"
                type="text"
                className="form-control"
                value="sentence-transformers/all-MiniLM-L6-v2"
                disabled
              />
              <span className="form-hint">Produces 384-dimensional dense semantic vectors</span>
            </div>

            <div className="form-group">
              <label htmlFor="vector-db">Vector Database Engine</label>
              <input
                id="vector-db"
                type="text"
                className="form-control"
                value="FAISS IndexFlatIP (Cosine Similarity)"
                disabled
              />
              <span className="form-hint">Local vector indexing and inner product search</span>
            </div>
          </div>
        </div>

        {/* Section 2: Application Settings */}
        <div className="enterprise-card settings-card">
          <div className="card-section-title">
            <SettingsIcon size={18} className="text-indigo" />
            <span>Application & Security Settings</span>
          </div>
          <p className="card-section-desc">
            General enterprise platform controls and privacy policies.
          </p>

          <div className="settings-form-grid">
            <div className="form-group">
              <label htmlFor="app-name">Application Name</label>
              <input
                id="app-name"
                type="text"
                className="form-control"
                value="Local Enterprise Policy Assistant"
                disabled
              />
            </div>

            <div className="form-group">
              <label htmlFor="api-url">Backend LLM Status Endpoint</label>
              <input
                id="api-url"
                type="text"
                className="form-control"
                value="http://localhost:8000/api/llm/status"
                disabled
              />
            </div>

            <div className="form-group">
              <label htmlFor="data-privacy">Data Privacy Mode</label>
              <input
                id="data-privacy"
                type="text"
                className="form-control"
                value="100% Local / Zero Cloud Exfiltration (No Cloud LLM Keys)"
                disabled
              />
            </div>
          </div>
        </div>

        {/* Section 3: Knowledge Base Settings */}
        <div className="enterprise-card settings-card">
          <div className="card-section-title">
            <Database size={18} className="text-purple" />
            <span>RAG Retrieval & Guardrail Parameters</span>
          </div>
          <p className="card-section-desc">
            Threshold filtering, context expansion, and citation controls.
          </p>

          <div className="settings-form-grid">
            <div className="form-group">
              <label htmlFor="min-score">Minimum Relevance Threshold</label>
              <input
                id="min-score"
                type="text"
                className="form-control"
                value="0.35 (Rejects Out-of-Domain Questions)"
                disabled
              />
            </div>

            <div className="form-group">
              <label htmlFor="top-k">Top-K Retrieved Context Chunks</label>
              <input
                id="top-k"
                type="text"
                className="form-control"
                value="5 Chunks"
                disabled
              />
            </div>

            <div className="form-group">
              <label htmlFor="max-chars">Max Context Buffer</label>
              <input
                id="max-chars"
                type="text"
                className="form-control"
                value="6,000 Characters"
                disabled
              />
            </div>
          </div>
        </div>

        {/* Section 4: System Information */}
        <div className="enterprise-card settings-card">
          <div className="card-section-title">
            <Server size={18} className="text-cyan" />
            <span>System Architecture</span>
          </div>
          <p className="card-section-desc">
            Runtime architecture and framework specifications.
          </p>

          <div className="system-info-list">
            <div className="info-row">
              <span className="info-key">Frontend Framework</span>
              <span className="info-val">React 19 &bull; Vite 8 &bull; JavaScript</span>
            </div>
            <div className="info-row">
              <span className="info-key">Backend Microservice</span>
              <span className="info-val">FastAPI 0.115 &bull; Uvicorn &bull; Python 3.14</span>
            </div>
            <div className="info-row">
              <span className="info-key">Project Phase</span>
              <span className="info-val">Phase 8 — Ollama Local LLM & RAG Answer Generation Complete</span>
            </div>
            <div className="info-row">
              <span className="info-key">Local LLM Engine</span>
              <span className="info-val">Ollama (llama3.2:3b / mistral / llama3)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
