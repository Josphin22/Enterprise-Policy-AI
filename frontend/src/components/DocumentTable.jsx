import React, { useState } from 'react';
import { FileText, Trash2, RefreshCw, Play, Inbox, Loader2, Layers, Eye } from 'lucide-react';
import { deleteDocument, processDocument } from '../services/api';
import ChunkInspectorModal from './ChunkInspectorModal';
import DocumentPreviewModal from './DocumentPreviewModal';

export default function DocumentTable({ documents = [], onRefresh, isLoading = false }) {
  const [deletingId, setDeletingId] = useState(null);
  const [processingId, setProcessingId] = useState(null);
  const [inspectingDoc, setInspectingDoc] = useState(null);
  const [previewingDoc, setPreviewingDoc] = useState(null);
  const [actionMessage, setActionMessage] = useState('');

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (isoString) => {
    if (!isoString) return '—';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoString;
    }
  };

  const handleDelete = async (docId, filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}" and all its extracted chunks?`)) return;

    setDeletingId(docId);
    setActionMessage('');

    const result = await deleteDocument(docId);
    setDeletingId(null);

    if (result.success) {
      setActionMessage(`Document "${filename}" deleted successfully.`);
      if (onRefresh) onRefresh();
    } else {
      alert(`Failed to delete document: ${result.error}`);
    }
  };

  const handleProcess = async (docId, filename) => {
    setProcessingId(docId);
    setActionMessage('');

    const result = await processDocument(docId);
    setProcessingId(null);

    if (result.success) {
      setActionMessage(`Document "${filename}" processed successfully into ${result.data?.chunk_count || 0} chunks.`);
      if (onRefresh) onRefresh();
    } else {
      alert(`Document processing failed: ${result.error}`);
      if (onRefresh) onRefresh();
    }
  };

  return (
    <div className="document-table-container">
      <div className="table-header-bar">
        <div>
          <h4>Uploaded Enterprise Documents</h4>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Real files managed by the local FastAPI backend & PostgreSQL
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span className="doc-count-badge">{documents.length} Documents</span>
          <button
            type="button"
            className={`btn-action-icon ${isLoading ? 'spin-animation' : ''}`}
            onClick={onRefresh}
            title="Refresh document repository"
            aria-label="Refresh document repository"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Action Notification Banner */}
      {actionMessage && (
        <div style={{ background: 'var(--color-online-bg)', border: '1px solid var(--color-online-border)', color: '#34d399', padding: '0.5rem 1rem', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem', marginBottom: '1rem' }}>
          {actionMessage}
        </div>
      )}

      {documents.length === 0 ? (
        <div className="empty-state-card" role="status" aria-label="No documents">
          <div className="empty-state-icon">
            <Inbox size={36} />
          </div>
          <h4 className="empty-state-title">No policy documents in repository</h4>
          <p className="empty-state-desc">
            Upload a policy document to start asking questions.
          </p>
        </div>
      ) : (
        <div className="table-responsive-wrapper">
          <table className="enterprise-data-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Size</th>
                <th>Status</th>
                <th>Chunks</th>
                <th>Uploaded Date</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => {
                const isProcessingThis = processingId === doc.document_id;
                const isDeletingThis = deletingId === doc.document_id;
                const isProcessed = doc.status === 'processed';

                return (
                  <tr key={doc.document_id}>
                    <td className="cell-filename">
                      <FileText size={16} color="var(--accent-cyan)" />
                      <span>{doc.filename}</span>
                    </td>
                    <td>
                      <span className="file-type-pill">{doc.file_type?.toUpperCase() || 'TXT'}</span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{formatFileSize(doc.size)}</td>
                    <td>
                      <span className={`status-pill status-${isProcessed ? 'ready' : doc.status === 'failed' ? 'error' : doc.status === 'processing' ? 'active' : 'pending'}`}>
                        {doc.status || 'uploaded'}
                      </span>
                    </td>
                    <td>
                      {isProcessed ? (
                        <button
                          type="button"
                          className="btn-chunk-badge"
                          onClick={() => setInspectingDoc(doc)}
                          title="Inspect chunks"
                        >
                          <Layers size={12} /> {doc.chunk_count} chunks
                        </button>
                      ) : doc.status === 'processing' ? (
                        <span style={{ fontSize: '0.78rem', color: 'var(--accent-cyan)' }}>Processing...</span>
                      ) : doc.status === 'failed' ? (
                        <span style={{ fontSize: '0.78rem', color: '#f87171' }}>Failed</span>
                      ) : (
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>0</span>
                      )}
                    </td>
                    <td style={{ fontSize: '0.78rem' }}>{formatDate(doc.uploaded_at)}</td>
                    <td style={{ textAlign: 'right' }}>
                      <div className="action-buttons-group">
                        <button
                          type="button"
                          className="btn-action-icon"
                          onClick={() => setPreviewingDoc(doc)}
                          title="Preview Extracted Document Content (Pages, Sections, Tables)"
                          aria-label="Preview document content"
                        >
                          <Eye size={14} />
                        </button>

                        <button
                          type="button"
                          className="btn-action-icon"
                          onClick={() => setInspectingDoc(doc)}
                          title="Inspect Extracted Chunks"
                          aria-label="Inspect chunks"
                        >
                          <Layers size={14} />
                        </button>

                        <button
                          type="button"
                          className={`btn-action-icon ${isProcessingThis ? 'spinning' : ''}`}
                          disabled={isProcessingThis || isDeletingThis}
                          onClick={() => handleProcess(doc.document_id, doc.filename)}
                          title={isProcessed ? "Reprocess Document" : "Process Document (Extract & Chunk)"}
                          aria-label="Process document"
                        >
                          {isProcessingThis ? <Loader2 size={14} className="spin-animation" /> : <Play size={14} />}
                        </button>

                        <button
                          type="button"
                          className="btn-action-icon btn-action-danger"
                          disabled={isDeletingThis || isProcessingThis}
                          onClick={() => handleDelete(doc.document_id, doc.filename)}
                          title="Delete document"
                          aria-label="Delete document"
                        >
                          {isDeletingThis ? <Loader2 size={14} className="spin-animation" /> : <Trash2 size={14} />}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Document Content Preview Modal */}
      <DocumentPreviewModal
        document={previewingDoc}
        isOpen={Boolean(previewingDoc)}
        onClose={() => setPreviewingDoc(null)}
      />

      {/* Chunks Inspector Modal */}
      <ChunkInspectorModal
        document={inspectingDoc}
        isOpen={Boolean(inspectingDoc)}
        onClose={() => setInspectingDoc(null)}
      />
    </div>
  );
}
