import React, { useState, useEffect } from 'react';
import {
  Database,
  Cpu,
  Layers,
  FileText,
  Clock,
  Play,
  HardDrive,
  Search,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  Sparkles,
  Tag,
  Hash,
} from 'lucide-react';
import StatusCard from '../components/StatusCard';
import { getKnowledgeBaseStatus, buildKnowledgeBase, searchKnowledgeBase } from '../services/api';

const SAMPLE_QUERIES = [
  'How many annual leave days are allowed?',
  'What are the standard core working hours?',
  'Can employees work from home and is there a subsidy?',
  'What is the policy for carrying over unused vacation days?',
];

export default function KnowledgeBase() {
  const [kbStatus, setKbStatus] = useState({
    status: 'not_built',
    documents: 0,
    processed_documents: 0,
    chunks: 0,
    vectors: 0,
    embedding_model: 'all-MiniLM-L6-v2',
    embedding_dimension: 384,
    vector_database: 'FAISS',
    last_built: null,
  });

  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isBuilding, setIsBuilding] = useState(false);
  const [buildStep, setBuildStep] = useState('');
  const [buildFeedback, setBuildFeedback] = useState(null);

  // Search testing state
  const [searchQuery, setSearchQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState(null);
  const [searchError, setSearchError] = useState(null);

  const fetchStatus = async () => {
    setIsLoadingStatus(true);
    const res = await getKnowledgeBaseStatus();
    if (res.success && res.data) {
      setKbStatus(res.data);
    }
    setIsLoadingStatus(false);
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleBuildKnowledgeBase = async () => {
    setIsBuilding(true);
    setBuildFeedback(null);

    // Visual step sequence
    setBuildStep('Reading processed chunks from PostgreSQL...');
    await new Promise((r) => setTimeout(r, 600));

    setBuildStep('Generating dense SentenceTransformer embeddings...');
    await new Promise((r) => setTimeout(r, 800));

    setBuildStep('Building FAISS IndexFlatIP & saving to disk...');

    const res = await buildKnowledgeBase();
    if (res.success && res.data?.success) {
      setBuildFeedback({
        type: 'success',
        message: `Knowledge Base successfully built! Indexed ${res.data.vectors} vectors across ${res.data.documents} documents (${res.data.embedding_dimension}-dim).`,
      });
      await fetchStatus();
    } else {
      setBuildFeedback({
        type: 'error',
        message: res.error || res.data?.message || 'Failed to build knowledge base.',
      });
    }

    setIsBuilding(false);
    setBuildStep('');
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    setSearchError(null);

    const res = await searchKnowledgeBase(searchQuery.trim(), topK);
    if (res.success) {
      setSearchResults(res.results);
    } else {
      setSearchError(res.error || 'Vector search failed. Ensure the knowledge base is built.');
      setSearchResults([]);
    }
    setIsSearching(false);
  };

  const handleSelectSample = (sampleText) => {
    setSearchQuery(sampleText);
  };

  const formatTimestamp = (ts) => {
    if (!ts) return 'Never / Not Built';
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  };

  const isReady = kbStatus.status === 'ready' && kbStatus.vectors > 0;

  return (
    <div className="knowledge-page-container">
      {/* Page Header */}
      <div className="page-header-intro">
        <div>
          <h1 className="page-main-heading">Vector Knowledge Base</h1>
          <p className="page-sub-heading">
            Convert processed document chunks into normalized vector embeddings using SentenceTransformers and index them in FAISS for semantic retrieval.
          </p>
        </div>
        <div className="header-action-group">
          <button
            type="button"
            className="btn-action-ghost"
            onClick={fetchStatus}
            disabled={isLoadingStatus}
            title="Refresh Knowledge Base Status"
          >
            <RefreshCw size={15} className={isLoadingStatus ? 'spin-icon' : ''} />
            <span>Refresh Status</span>
          </button>
        </div>
      </div>

      {/* Main Knowledge Base Stats Grid */}
      <div className="metrics-cards-grid">
        <StatusCard
          title="Indexed Documents"
          value={`${kbStatus.processed_documents} / ${kbStatus.documents}`}
          subtitle="Processed documents with valid text chunks"
          icon={FileText}
          badgeText={kbStatus.processed_documents > 0 ? "Chunks Available" : "Upload Documents"}
          badgeType={kbStatus.processed_documents > 0 ? "success" : "neutral"}
        />

        <StatusCard
          title="FAISS Vectors"
          value={isReady ? `${kbStatus.vectors} Vectors` : "0 (Not Built)"}
          subtitle={`Indexed in local ${kbStatus.vector_database} index`}
          icon={Layers}
          badgeText={isReady ? "Index Active" : "Build Required"}
          badgeType={isReady ? "success" : "warning"}
        />

        <StatusCard
          title="Embedding Model"
          value={kbStatus.embedding_model || "all-MiniLM-L6-v2"}
          subtitle={`${kbStatus.embedding_dimension || 384}-dimensional dense vectors`}
          icon={Cpu}
          badgeText="Local PyTorch"
          badgeType="info"
        />

        <StatusCard
          title="Vector Engine"
          value="FAISS IndexFlatIP"
          subtitle="Cosine similarity via normalized inner product"
          icon={Database}
          badgeText="Local CPU"
          badgeType="info"
        />

        <StatusCard
          title="Last Build Timestamp"
          value={formatTimestamp(kbStatus.last_built)}
          subtitle="Timestamp of most recent FAISS index build"
          icon={Clock}
          badgeText={kbStatus.last_built ? "Persistent" : "Pending Build"}
          badgeType={kbStatus.last_built ? "neutral" : "warning"}
        />

        <StatusCard
          title="Vector Persistence"
          value="backend/vectorstore"
          subtitle="index.faiss & metadata.json disk store"
          icon={HardDrive}
          badgeText="Persistent Disk"
          badgeType="info"
        />
      </div>

      {/* Knowledge Base Build & Management Panel */}
      <div className="enterprise-card kb-action-panel">
        <div className="card-section-title">
          <Database size={18} className="text-cyan" />
          <span>Knowledge Base Construction & Re-Indexing</span>
        </div>
        <p className="card-section-desc">
          Extracts text from all processed document chunks in PostgreSQL, computes dense numerical embeddings via <strong>{kbStatus.embedding_model}</strong>, normalizes them, and serializes the <strong>FAISS IndexFlatIP</strong> index and chunk metadata mapping to disk.
        </p>

        {buildFeedback && (
          <div className={`kb-feedback-banner ${buildFeedback.type === 'success' ? 'feedback-success' : 'feedback-error'}`}>
            {buildFeedback.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
            <span>{buildFeedback.message}</span>
          </div>
        )}

        <div className="kb-action-controls">
          <button
            type="button"
            className="btn-kb-build"
            onClick={handleBuildKnowledgeBase}
            disabled={isBuilding || kbStatus.processed_documents === 0}
            title={kbStatus.processed_documents === 0 ? "Process at least one document first" : "Build / Rebuild FAISS Vector Index"}
          >
            {isBuilding ? (
              <>
                <Loader2 size={16} className="spin-icon" />
                <span>{buildStep || 'Building Knowledge Base...'}</span>
              </>
            ) : (
              <>
                <Play size={16} />
                <span>{isReady ? 'Rebuild Knowledge Base' : 'Build Knowledge Base'}</span>
              </>
            )}
          </button>

          {kbStatus.processed_documents === 0 && (
            <span className="kb-disabled-hint">
              Upload and process documents in the Documents page before building the vector database.
            </span>
          )}
          {isReady && !isBuilding && (
            <span className="kb-ready-badge">
              <CheckCircle2 size={14} /> Knowledge Base Online & Searchable
            </span>
          )}
        </div>

        <div className="kb-specifications-box">
          <div className="spec-item">
            <span className="spec-label">Model Architecture:</span>
            <span className="spec-value">SentenceTransformers ({kbStatus.embedding_model})</span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Vector Dimension:</span>
            <span className="spec-value">{kbStatus.embedding_dimension || 384} float32 components</span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Similarity Metric:</span>
            <span className="spec-value">Normalized Inner Product (Cosine Similarity)</span>
          </div>
          <div className="spec-item">
            <span className="spec-label">Persistence Path:</span>
            <span className="spec-value"><code>backend/vectorstore/index.faiss</code></span>
          </div>
        </div>
      </div>

      {/* Semantic Search Testing Console */}
      <div className="enterprise-card kb-search-test-panel">
        <div className="card-section-title">
          <Search size={18} className="text-cyan" />
          <span>Test Semantic Search Retrieval (Phase 6 Verification)</span>
        </div>
        <p className="card-section-desc">
          Test similarity retrieval against the FAISS vector index. The query is embedded in real-time, normalized, and ranked against indexed policy chunks by cosine similarity score.
        </p>

        {/* Sample Query Chips */}
        <div className="sample-chips-container">
          <span className="chips-label">Quick test queries:</span>
          {SAMPLE_QUERIES.map((sample, idx) => (
            <button
              key={idx}
              type="button"
              className="query-chip"
              onClick={() => handleSelectSample(sample)}
            >
              <Sparkles size={12} />
              <span>{sample}</span>
            </button>
          ))}
        </div>

        {/* Search Input Form */}
        <form onSubmit={handleSearch} className="search-form-row">
          <div className="search-input-wrapper">
            <Search size={18} className="search-input-icon" />
            <input
              type="text"
              className="search-text-input"
              placeholder="Enter a natural language policy question (e.g. How many annual leave days are allowed?)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              disabled={isSearching}
            />
          </div>

          <div className="topk-selector-wrapper">
            <label htmlFor="topk-select">Top-K:</label>
            <select
              id="topk-select"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              disabled={isSearching}
            >
              <option value={1}>1 Chunk</option>
              <option value={3}>3 Chunks</option>
              <option value={5}>5 Chunks</option>
              <option value={10}>10 Chunks</option>
            </select>
          </div>

          <button
            type="submit"
            className="btn-search-submit"
            disabled={isSearching || !searchQuery.trim()}
          >
            {isSearching ? (
              <>
                <Loader2 size={16} className="spin-icon" />
                <span>Searching...</span>
              </>
            ) : (
              <>
                <Search size={16} />
                <span>Search</span>
              </>
            )}
          </button>
        </form>

        {/* Error Alert */}
        {searchError && (
          <div className="kb-feedback-banner feedback-error">
            <AlertCircle size={18} />
            <span>{searchError}</span>
          </div>
        )}

        {/* Search Results Display */}
        {searchResults && (
          <div className="search-results-section">
            <div className="results-header">
              <h3>Top Retrieved Document Chunks ({searchResults.length})</h3>
              <span className="results-subtext">Ranked by Cosine Similarity Score</span>
            </div>

            {searchResults.length === 0 ? (
              <div className="empty-results-box">
                <AlertCircle size={24} />
                <p>No matching chunks found in the vector database.</p>
              </div>
            ) : (
              <div className="results-cards-list">
                {searchResults.map((result, idx) => {
                  const scorePct = Math.round(Math.max(0, result.score) * 100);
                  return (
                    <div key={idx} className="search-result-card">
                      <div className="result-card-header">
                        <div className="result-meta-tags">
                          <span className="result-rank-badge">#{idx + 1}</span>
                          <span className="result-doc-badge">
                            <FileText size={13} />
                            {result.filename || 'Document'}
                          </span>
                          {result.page && (
                            <span className="result-page-badge">
                              Page {result.page}
                            </span>
                          )}
                          {result.section && (
                            <span className="result-section-badge">
                              <Tag size={12} />
                              {result.section}
                            </span>
                          )}
                        </div>

                        <div className="similarity-score-container" title={`Exact Cosine Score: ${result.score}`}>
                          <div className="score-text">
                            <span className="score-label">Similarity:</span>
                            <span className="score-value">{scorePct}%</span>
                          </div>
                          <div className="score-bar-bg">
                            <div
                              className="score-bar-fill"
                              style={{ width: `${scorePct}%` }}
                            />
                          </div>
                        </div>
                      </div>

                      <div className="result-chunk-text">
                        <pre className="chunk-preformatted-text">{result.text}</pre>
                      </div>

                      <div className="result-card-footer">
                        <span className="chunk-id-tag">
                          <Hash size={11} /> Chunk ID: {result.chunk_id || 'N/A'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
