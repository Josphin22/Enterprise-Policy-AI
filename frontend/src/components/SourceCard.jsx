import React, { useState } from 'react';
import { FileText, Bookmark, Hash, Layers, AlertCircle, ChevronDown, ChevronUp, Quote } from 'lucide-react';

export default function SourceCard({ sources = [], status = 'idle' }) {
  const [expandedSources, setExpandedSources] = useState({});

  const toggleExpand = (key) => {
    setExpandedSources((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

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
        <h4 className="source-card-empty-title">Document Citations</h4>
        <p className="source-card-empty-desc">
          When you ask a question, the specific document sections and policies referenced will be displayed here.
        </p>
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

      <div className="source-list" role="feed" aria-label="Retrieved Sources">
        {sources.map((source, index) => {
          const scorePercent = source.score !== undefined ? Math.round(source.score * 100) : null;
          const sourceId = source.source_id || `S${index + 1}`;
          const docName = source.document || source.filename || 'Enterprise Document';
          const cardKey = source.chunk_id || `source-${index}`;
          const isExpanded = !!expandedSources[cardKey];
          const previewText = source.preview || source.snippet || source.text || '';

          return (
            <div 
              key={cardKey} 
              data-source-id={sourceId}
              className={`source-item ${isExpanded ? 'source-item-expanded' : ''}`}
              tabIndex={0}
              role="article"
              aria-expanded={isExpanded}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  toggleExpand(cardKey);
                }
              }}
            >
              <div
                className="source-item-meta"
                onClick={() => toggleExpand(cardKey)}
                style={{ cursor: previewText ? 'pointer' : 'default' }}
                title={previewText ? 'Click to toggle preview excerpt' : ''}
              >
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
                  {source.chunk_index !== undefined && source.chunk_index !== null && (
                    <span className="source-page-badge" title={`Chunk Index: ${source.chunk_index}`}>
                      Chunk #{source.chunk_index}
                    </span>
                  )}
                  {source.section && (
                    <span className="source-section-badge" title={`Section: ${source.section}`}>
                      <Layers size={11} /> {source.section}
                    </span>
                  )}
                  {scorePercent !== null && (
                    <span className="source-score-badge" title="Vector cosine similarity to search query">
                      Relevance: {scorePercent}%
                    </span>
                  )}
                  {previewText && (
                    <button
                      type="button"
                      className="source-expand-btn"
                      aria-label={isExpanded ? "Collapse excerpt" : "Expand excerpt"}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleExpand(cardKey);
                      }}
                    >
                      {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    </button>
                  )}
                </div>
              </div>

              {source.score !== undefined && (
                <div className="source-score-meter-wrap" aria-label={`Similarity score ${scorePercent}%`}>
                  <div
                    className="source-score-meter-fill"
                    style={{ width: `${Math.max(5, Math.min(100, scorePercent))}%` }}
                  ></div>
                </div>
              )}

              {/* Expandable Preview Excerpt */}
              {isExpanded && previewText && (
                <div className="source-preview-box" aria-label="Document excerpt text">
                  <div className="source-preview-header">
                    <Quote size={12} className="text-cyan" />
                    <span>Relevant Excerpt ({docName}{source.page ? `, p. ${source.page}` : ''})</span>
                  </div>
                  <p className="source-preview-text">{previewText}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
