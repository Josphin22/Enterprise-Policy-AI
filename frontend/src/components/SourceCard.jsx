import React from 'react';
import { FileText, Bookmark, Hash, Layers, ShieldCheck, AlertCircle } from 'lucide-react';

export default function SourceCard({ sources = [], status = 'idle' }) {
  if (status === 'insufficient_context') {
    return (
      <div className="source-card-container empty-state-box">
        <div className="source-card-empty-icon text-amber">
          <AlertCircle size={24} />
        </div>
        <h4 className="source-card-empty-title">Insufficient Context</h4>
        <p className="source-card-empty-desc">
          No document passages met the relevance threshold (0.35) for the current query.
        </p>
        <span className="source-card-phase-note">
          Hallucination Prevention Guardrail Active
        </span>
      </div>
    );
  }

  if (!sources || sources.length === 0) {
    return (
      <div className="source-card-container empty-state-box">
        <div className="source-card-empty-icon">
          <Bookmark size={24} />
        </div>
        <h4 className="source-card-empty-title">Retrieved Document Sources</h4>
        <p className="source-card-empty-desc">
          Source cards will appear here with page numbers and cosine similarity scores when you submit a question.
        </p>
        <span className="source-card-phase-note">
          Phase 7 Verifiable Citations Enabled
        </span>
      </div>
    );
  }

  return (
    <div className="source-card-container">
      <div className="source-card-header">
        <h4 className="source-card-title">
          <Bookmark size={16} className="text-cyan" />
          Referenced Sources ({sources.length})
        </h4>
        <span className="source-count-pill">{sources.length} cited</span>
      </div>

      <div className="source-list">
        {sources.map((source, index) => {
          const scorePercent = source.score !== undefined ? Math.round(source.score * 100) : null;
          const sourceId = source.source_id || `S${index + 1}`;
          const docName = source.document || source.filename || 'Enterprise Document';

          return (
            <div key={source.chunk_id || index} className="source-item">
              <div className="source-item-meta">
                <div className="source-tag-group">
                  <span className="source-id-badge">[{sourceId}]</span>
                  <span className="source-filename" title={docName}>
                    <FileText size={13} />
                    {docName}
                  </span>
                </div>

                <div className="source-badges-row">
                  {source.page !== null && source.page !== undefined && (
                    <span className="source-page-badge">
                      <Hash size={11} /> Page {source.page}
                    </span>
                  )}
                  {source.section && (
                    <span className="source-section-badge" title={source.section}>
                      <Layers size={11} /> {source.section}
                    </span>
                  )}
                  {scorePercent !== null && (
                    <span className="source-score-badge">
                      {scorePercent}% match
                    </span>
                  )}
                </div>
              </div>

              {source.score !== undefined && (
                <div className="source-score-meter-wrap">
                  <div
                    className="source-score-meter-fill"
                    style={{ width: `${Math.max(5, Math.min(100, scorePercent))}%` }}
                  ></div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
