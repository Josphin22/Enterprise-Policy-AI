import React, { useState, useEffect } from 'react';
import { X, Eye, FileText, Search, Loader2, Table, Sparkles, Hash, Globe, AlertCircle } from 'lucide-react';
import { getDocumentPreview } from '../services/api';

export default function DocumentPreviewModal({ document: doc, isOpen, onClose }) {
  const [previewData, setPreviewData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('pages');
  const [searchFilter, setSearchFilter] = useState('');

  useEffect(() => {
    if (isOpen && (doc?.document_id || doc?.id)) {
      const docId = doc.document_id || doc.id;
      setIsLoading(true);
      setError(null);
      getDocumentPreview(docId).then((res) => {
        setIsLoading(false);
        if (res.success && res.data) {
          setPreviewData(res.data);
        } else {
          setError(res.error || 'Failed to load document preview');
        }
      });
    } else {
      setPreviewData(null);
    }
  }, [isOpen, doc]);

  if (!isOpen || !doc) return null;

  const pages = previewData?.pages || [];
  const chunks = previewData?.chunks || [];
  const sections = previewData?.sections || [];

  const filteredPages = pages.filter((p) => {
    if (!searchFilter.trim()) return true;
    const q = searchFilter.toLowerCase();
    return (
      (p.text && p.text.toLowerCase().includes(q)) ||
      (p.section && p.section.toLowerCase().includes(q)) ||
      (p.page_number && String(p.page_number).includes(q))
    );
  });

  const filteredChunks = chunks.filter((c) => {
    if (!searchFilter.trim()) return true;
    const q = searchFilter.toLowerCase();
    return (
      (c.text && c.text.toLowerCase().includes(q)) ||
      (c.section && c.section.toLowerCase().includes(q)) ||
      String(c.chunk_index).includes(q)
    );
  });

  return (
    <div className="modal-backdrop-overlay" onClick={onClose}>
      <div
        className="modal-content-card chunk-modal"
        style={{ maxWidth: '880px', width: '92vw' }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {/* Modal Header */}
        <div className="modal-header-bar">
          <div className="modal-title-group">
            <Eye size={22} className="text-cyan" />
            <div>
              <h3>Document Content Preview</h3>
              <p>
                <strong>{doc.filename || previewData?.filename}</strong> &bull; Status:{' '}
                <span className={`status-pill status-${doc.status === 'processed' ? 'ready' : 'pending'}`}>
                  {previewData?.status || doc.status}
                </span>
              </p>
            </div>
          </div>
          <button className="btn-modal-close" onClick={onClose} aria-label="Close modal">
            <X size={18} />
          </button>
        </div>

        {/* Intelligence Metadata Bar */}
        {previewData && (
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0.75rem',
            padding: '0.75rem 1.25rem',
            background: 'var(--bg-secondary, rgba(255,255,255,0.03))',
            borderBottom: '1px solid var(--border-color, rgba(255,255,255,0.08))',
            fontSize: '0.8rem',
            alignItems: 'center'
          }}>
            {previewData.page_count !== null && previewData.page_count !== undefined && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: 'var(--text-secondary)' }}>
                <FileText size={14} /> {previewData.page_count} {previewData.page_count === 1 ? 'Page' : 'Pages'}
              </span>
            )}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: 'var(--text-secondary)' }}>
              <Hash size={14} /> {previewData.total_chunks || chunks.length} Chunks
            </span>
            {previewData.table_count > 0 && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: '#38bdf8' }}>
                <Table size={14} /> {previewData.table_count} {previewData.table_count === 1 ? 'Table' : 'Tables'} Detected
              </span>
            )}
            {previewData.ocr_applied && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: '#a855f7' }}>
                <Sparkles size={14} /> OCR Applied
              </span>
            )}
            {previewData.language && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: '#10b981' }}>
                <Globe size={14} /> Language: {previewData.language.toUpperCase()}
              </span>
            )}
          </div>
        )}

        {/* Section Tags */}
        {sections.length > 0 && (
          <div style={{ padding: '0.5rem 1.25rem', display: 'flex', flexWrap: 'wrap', gap: '0.4rem', borderBottom: '1px solid var(--border-color, rgba(255,255,255,0.06))' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', alignSelf: 'center' }}>Sections:</span>
            {sections.map((sec, idx) => (
              <span
                key={idx}
                style={{
                  fontSize: '0.72rem',
                  padding: '0.2rem 0.55rem',
                  borderRadius: '999px',
                  background: 'rgba(56, 189, 248, 0.12)',
                  color: '#38bdf8',
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                }}
              >
                {sec}
              </span>
            ))}
          </div>
        )}

        {/* Tab Selector & Search Toolbar */}
        <div className="modal-toolbar-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '0.75rem 1.25rem', gap: '1rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className={`btn-action-icon ${activeTab === 'pages' ? 'active' : ''}`}
              style={{
                padding: '0.4rem 0.85rem',
                borderRadius: 'var(--radius-sm, 6px)',
                background: activeTab === 'pages' ? 'var(--color-accent-blue, #2563eb)' : 'rgba(255,255,255,0.05)',
                color: '#fff',
                fontSize: '0.8rem',
                cursor: 'pointer',
              }}
              onClick={() => setActiveTab('pages')}
            >
              Page-by-Page View ({pages.length})
            </button>
            <button
              className={`btn-action-icon ${activeTab === 'chunks' ? 'active' : ''}`}
              style={{
                padding: '0.4rem 0.85rem',
                borderRadius: 'var(--radius-sm, 6px)',
                background: activeTab === 'chunks' ? 'var(--color-accent-blue, #2563eb)' : 'rgba(255,255,255,0.05)',
                color: '#fff',
                fontSize: '0.8rem',
                cursor: 'pointer',
              }}
              onClick={() => setActiveTab('chunks')}
            >
              Chunk-Level View ({chunks.length})
            </button>
          </div>

          <div style={{ position: 'relative', width: '240px' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Search extracted text..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              style={{
                width: '100%',
                padding: '0.4rem 0.5rem 0.4rem 2rem',
                fontSize: '0.8rem',
                borderRadius: 'var(--radius-sm, 6px)',
                background: 'rgba(0,0,0,0.2)',
                border: '1px solid var(--border-color, rgba(255,255,255,0.15))',
                color: '#fff',
              }}
            />
          </div>
        </div>

        {/* Content Body */}
        <div className="modal-body-scrollable" style={{ maxHeight: '55vh', overflowY: 'auto', padding: '1rem 1.25rem' }}>
          {isLoading && (
            <div style={{ textAlign: 'center', padding: '3rem' }}>
              <Loader2 size={28} className="spin-animation" style={{ margin: '0 auto 0.5rem', color: '#38bdf8' }} />
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Extracting and rendering document preview...</p>
            </div>
          )}

          {error && (
            <div style={{ display: 'flex', gap: '0.5rem', color: '#ef4444', background: 'rgba(239,68,68,0.1)', padding: '1rem', borderRadius: '6px' }}>
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          {!isLoading && !error && activeTab === 'pages' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {filteredPages.length === 0 ? (
                <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>No pages found matching filter.</p>
              ) : (
                filteredPages.map((page, idx) => (
                  <div
                    key={idx}
                    style={{
                      border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
                      borderRadius: '8px',
                      background: 'rgba(255,255,255,0.02)',
                      padding: '1rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#38bdf8' }}>
                        {page.page_number ? `Page ${page.page_number}` : `Section Block ${idx + 1}`}
                      </span>
                      {page.section && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.05)', padding: '0.15rem 0.5rem', borderRadius: '4px' }}>
                          {page.section}
                        </span>
                      )}
                    </div>
                    <pre style={{
                      whiteSpace: 'pre-wrap',
                      fontFamily: 'inherit',
                      fontSize: '0.82rem',
                      lineHeight: '1.5',
                      color: 'var(--text-primary, #e2e8f0)',
                      margin: 0,
                    }}>
                      {page.text}
                    </pre>
                  </div>
                ))
              )}
            </div>
          )}

          {!isLoading && !error && activeTab === 'chunks' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {filteredChunks.length === 0 ? (
                <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>No chunks found matching filter.</p>
              ) : (
                filteredChunks.map((c) => (
                  <div
                    key={c.chunk_index}
                    style={{
                      border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
                      borderRadius: '6px',
                      background: 'rgba(255,255,255,0.02)',
                      padding: '0.75rem 1rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem', fontSize: '0.78rem' }}>
                      <span style={{ color: '#38bdf8', fontWeight: 600 }}>Chunk #{c.chunk_index}</span>
                      <div style={{ display: 'flex', gap: '0.75rem', color: 'var(--text-muted)' }}>
                        {c.page_number && <span>Page {c.page_number}</span>}
                        {c.section && <span>Section: {c.section}</span>}
                        <span>{c.character_count} chars</span>
                      </div>
                    </div>
                    <p style={{ margin: 0, fontSize: '0.82rem', lineHeight: '1.45', color: 'var(--text-primary)' }}>
                      {c.text}
                    </p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div style={{ padding: '0.75rem 1.25rem', borderTop: '1px solid var(--border-color, rgba(255,255,255,0.08))', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '0.45rem 1.25rem',
              borderRadius: '6px',
              background: 'rgba(255,255,255,0.1)',
              border: 'none',
              color: '#fff',
              fontSize: '0.82rem',
              cursor: 'pointer',
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
