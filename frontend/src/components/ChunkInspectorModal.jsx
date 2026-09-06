import React, { useState, useEffect } from 'react';
import { X, Layers, FileText, Search, Loader2, AlertCircle } from 'lucide-react';
import { getDocumentChunks } from '../services/api';

export default function ChunkInspectorModal({ document: doc, isOpen, onClose }) {
  const [chunks, setChunks] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen && doc?.document_id) {
      setIsLoading(true);
      setError(null);
      getDocumentChunks(doc.document_id).then((res) => {
        setIsLoading(false);
        if (res.success) {
          setChunks(res.chunks || []);
        } else {
          setError(res.error || 'Failed to load document chunks');
        }
      });
    } else {
      setChunks([]);
    }
  }, [isOpen, doc]);

  if (!isOpen || !doc) return null;

  const filteredChunks = chunks.filter((c) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      c.text?.toLowerCase().includes(query) ||
      c.section?.toLowerCase().includes(query) ||
      String(c.chunk_index).includes(query)
    );
  });

  return (
    <div className="modal-backdrop-overlay" onClick={onClose}>
      <div
        className="modal-content-card chunk-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Modal Header */}
        <div className="modal-header-bar">
          <div className="modal-title-group">
            <Layers size={20} className="text-cyan" />
            <div>
              <h3>Extracted Chunks Inspector</h3>
              <p>Document: <strong>{doc.filename}</strong> &bull; Status: <span className={`status-pill status-${doc.status === 'processed' ? 'ready' : 'pending'}`}>{doc.status}</span></p>
            </div>
          </div>
          <button className="btn-modal-close" onClick={onClose} aria-label="Close modal">
            <X size={18} />
          </button>
        </div>

        {/* Search and Summary Bar */}
        <div className="chunk-modal-toolbar">
          <div className="search-input-wrap">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              className="history-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search within extracted chunks or sections..."
            />
          </div>
          <div className="chunk-stat-badge">
            {chunks.length} Total Chunks ({filteredChunks.length} shown)
          </div>
        </div>

        {/* Chunks List Body */}
        <div className="chunk-modal-body">
          {isLoading ? (
            <div className="modal-loading-state">
              <Loader2 size={32} className="spin-animation text-cyan" />
              <p>Loading partitioned chunks from PostgreSQL...</p>
            </div>
          ) : error ? (
            <div className="modal-error-state">
              <AlertCircle size={32} className="text-danger" />
              <p>{error}</p>
            </div>
          ) : chunks.length === 0 ? (
            <div className="modal-empty-state">
              <FileText size={36} />
              <h4>No chunks extracted yet</h4>
              <p>Click "Process Document" in the repository table to extract and partition this file.</p>
            </div>
          ) : (
            <div className="chunks-flow-list">
              {filteredChunks.map((chunk) => (
                <div key={chunk.chunk_id || chunk.chunk_index} className="chunk-card">
                  <div className="chunk-card-meta">
                    <span className="chunk-index-badge">Chunk #{chunk.chunk_index + 1}</span>
                    {chunk.page !== null && chunk.page !== undefined && (
                      <span className="chunk-page-badge">Page {chunk.page}</span>
                    )}
                    {chunk.section && (
                      <span className="chunk-section-badge">Section: {chunk.section}</span>
                    )}
                    <span className="chunk-char-count">{chunk.character_count} chars</span>
                  </div>
                  <div className="chunk-text-box">
                    {chunk.text}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer-bar">
          <button className="btn-filter-pill" onClick={onClose}>
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
